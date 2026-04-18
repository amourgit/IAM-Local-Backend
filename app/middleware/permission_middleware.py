"""
Middleware de vérification des permissions — mode FIREWALL.
- Endpoint non enregistré → 403 rejeté
- Endpoint enregistré → vérifier UUIDs permissions
- Normalisation des paths : UUIDs remplacés par {id}
"""

import re
import logging
from fastapi import Request
from fastapi.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware

logger = logging.getLogger(__name__)

# UUID pattern pour normalisation des paths
UUID_PATTERN = re.compile(
    r"[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}",
    re.IGNORECASE,
)

# Chemins qui bypass complètement le middleware
PATHS_PUBLICS = {
    "/",
    "/health",
    "/docs",
    "/redoc",
    "/openapi.json",
    "/api/v1/tokens/login",
    "/api/v1/tokens/refresh",
    "/api/v1/gateway/forward",
    "/api/v1/gateway/modules",
    # ── Enregistrement inter-modules (service-to-service, sans token) ──
    "/api/v1/permissions/enregistrer",
    "/api/v1/endpoints/register",
}

PREFIXES_PUBLICS = (
    "/docs/",
    "/redoc/",
    "/_statics/",
    "/api/v1/health",
)


def normaliser_path(path: str) -> str:
    """Remplace les UUIDs dans un path par le placeholder {id}."""
    return UUID_PATTERN.sub("{id}", path)


class PermissionMiddleware(BaseHTTPMiddleware):
    """
    Middleware FIREWALL de vérification des permissions.

    Flux :
    1. Path public → bypass
    2. Extraire et valider le token JWT
    3. Admin (iam.admin) → bypass total
    4. Normaliser le path (UUIDs → {id})
    5. Chercher endpoint dans endpoint_permissions
    6. Introuvable → 403 REJETÉ (firewall)
    7. public=True → accès libre
    8. Comparer UUIDs token vs UUIDs endpoint (intersection)
    """

    async def dispatch(self, request: Request, call_next):
        path   = request.url.path
        method = request.method.upper()

        # ── 1. Bypass publics ─────────────────────────────────────
        if path in PATHS_PUBLICS or path.startswith(PREFIXES_PUBLICS):
            return await call_next(request)

        # ── 2. Token ──────────────────────────────────────────────
        current_user = await self._get_current_user(request)
        if current_user is None:
            return JSONResponse(
                status_code = 401,
                content     = {"detail": "Token de session manquant ou invalide."}
            )

        # ── 3. Normaliser le path ─────────────────────────────────
        path_normalise = normaliser_path(path)

        # ── 4. Config endpoint ────────────────────────────────────
        ep_config = await self._get_endpoint_config(path_normalise, method)

        # ── 5. FIREWALL — endpoint non enregistré → rejeté ────────
        if ep_config is None:
            logger.info(
                f"FIREWALL: endpoint non enregistré rejeté "
                f"user={current_user.get('profil_id')} "
                f"path={method} {path} (normalisé: {path_normalise})"
            )
            return JSONResponse(
                status_code = 403,
                content     = {
                    "detail" : "Accès refusé : endpoint non autorisé.",
                    "path"   : path,
                    "method" : method,
                }
            )

        # ── 6. Endpoint public ────────────────────────────────────
        if ep_config.get("public", False):
            request.state.current_user = current_user
            return await call_next(request)

        # ── 7. Vérification UUIDs ─────────────────────────────────
        required_uuids = set(str(u) for u in ep_config.get("permission_uuids", []))
        user_uuids     = set(current_user.get("permissions", []))

        if not required_uuids:
            # Endpoint enregistré sans permission requise → authentifié suffit
            request.state.current_user = current_user
            return await call_next(request)

        if not user_uuids.intersection(required_uuids):
            logger.info(
                f"Accès refusé: user={current_user.get('profil_id')} "
                f"path={method} {path_normalise} "
                f"user_permissions={current_user.get('permission_codes', [])}"
            )
            return JSONResponse(
                status_code = 403,
                content     = {
                    "detail" : "Permission insuffisante pour accéder à cette ressource.",
                    "path"   : path,
                    "method" : method,
                }
            )

        # ── 8. Accès autorisé ─────────────────────────────────────
        request.state.current_user = current_user
        return await call_next(request)

    async def _get_current_user(self, request: Request) -> dict | None:
        try:
            auth_header = request.headers.get("Authorization", "")
            if not auth_header.startswith("Bearer "):
                return None
            token = auth_header.split(" ", 1)[1].strip()
            if not token:
                return None

            import jwt
            from app.config import settings

            payload = jwt.decode(
                token,
                settings.JWT_SECRET_KEY,
                algorithms=[settings.JWT_ALGORITHM],
            )

            return {
                "profil_id"        : payload.get("sub"),
                "permissions"      : payload.get("permissions", []),
                "permission_codes" : payload.get("permission_codes", []),
                "roles"            : payload.get("roles", []),
                "type_profil"      : payload.get("type_profil"),
                "statut"           : payload.get("statut"),
                "is_bootstrap"     : payload.get("is_bootstrap", False),
                "user_id_national" : payload.get("user_id_national"),
            }

        except Exception as e:
            logger.debug(f"Token invalide: {e}")
            return None

    def _is_admin(self, user: dict) -> bool:
        """iam.admin bypass total. Bootstrap limité par ses permissions."""
        if user.get("is_bootstrap", False):
            return False
        return "iam.admin" in user.get("roles", [])

    async def _get_endpoint_config(self, path: str, method: str) -> dict | None:
        try:
            from app.database import AsyncSessionLocal
            from app.repositories.endpoint_permission import EndpointPermissionRepository

            async with AsyncSessionLocal() as db:
                repo   = EndpointPermissionRepository(db)
                result = await repo.get_by_path_method_any_source(path, method)
                if result:
                    return {
                        "permission_uuids" : result.permission_uuids,
                        "public"           : result.public,
                        "actif"            : result.actif,
                    }
                return None

        except Exception as e:
            logger.error(f"Erreur lecture endpoint config: {e}")
            return None
