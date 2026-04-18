"""
Service Gateway — cœur du routage IAM Local.
Vérifie les permissions puis route la requête vers le module métier.
"""

import logging
import httpx
from typing import Any, Dict, Optional
from uuid import UUID
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.module_registry import get_module_url, is_module_known
from app.core.exceptions import (
    PermissionDeniedError,
    NotFoundError,
    ValidationError,
)
from app.repositories.endpoint_permission import EndpointPermissionRepository
from app.repositories.permission import PermissionSourceRepository
from app.schemas.gateway import GatewayRequestSchema, GatewayResponseSchema
from app.middleware.auth import CurrentUser

logger = logging.getLogger(__name__)

# Timeout pour les appels vers les modules métier (secondes)
MODULE_REQUEST_TIMEOUT = 30.0

# Méthodes HTTP supportées
METHODES_SUPPORTEES = {"GET", "POST", "PUT", "PATCH", "DELETE", "HEAD"}


class GatewayService:
    """
    Orchestre la vérification des permissions et le routage
    vers les modules métier.
    """

    def __init__(self, db: AsyncSession):
        self.db       = db
        self.ep_repo  = EndpointPermissionRepository(db)
        self.src_repo = PermissionSourceRepository(db)

    async def forward(
        self,
        request : GatewayRequestSchema,
        user    : CurrentUser,
    ) -> GatewayResponseSchema:
        """
        Point d'entrée principal du gateway.

        1. Valider la requête
        2. Vérifier les permissions
        3. Router vers le module
        4. Retourner la réponse
        """
        method = request.method.upper()
        module = request.module.lower()
        path   = request.path

        # ── Étape 1 : Validations basiques ───────────────────────
        if method not in METHODES_SUPPORTEES:
            raise ValidationError(f"Méthode non supportée: {method}")

        if not path.startswith("/"):
            raise ValidationError(f"Le path doit commencer par /: {path}")

        if not is_module_known(module):
            return GatewayResponseSchema(
                success     = False,
                status_code = 404,
                error       = f"Module '{module}' inconnu.",
                module      = module,
                path        = path,
                method      = method,
            )

        # ── Étape 2 : Vérification des permissions ────────────────
        # Les admins bypass la vérification
        try:
            await self._verifier_permissions(
                module = module,
                path   = path,
                method = method,
                user   = user,
            )
        except PermissionDeniedError as e:
            return GatewayResponseSchema(
                success     = False,
                status_code = 403,
                error       = str(e),
                module      = module,
                path        = path,
                method      = method,
            )
            

        # ── Étape 3 : Construire les headers de contexte ──────────
        context_headers = self._build_context_headers(user)
        if request.headers:
            # Fusionner avec les headers additionnels du frontend
            # Les headers de contexte IAM ont priorité
            context_headers = {**request.headers, **context_headers}

        # ── Étape 4 : Router vers le module ───────────────────────
        response = await self._call_module(
            module  = module,
            path    = path,
            method  = method,
            body    = request.body,
            params  = request.params,
            headers = context_headers,
        )

        return response

    async def _verifier_permissions(
        self,
        module : str,
        path   : str,
        method : str,
        user   : CurrentUser,
    ) -> None:
        """
        Vérifie que l'utilisateur a les permissions requises
        pour accéder à cet endpoint du module.
        """
        # Récupérer la source du module
        source = await self.src_repo.get_by_code(module)
        if not source:
            # Module non enregistré dans IAM — on bloque par sécurité
            logger.warning(
                f"Module '{module}' non enregistré dans IAM Local. "
                f"Accès bloqué pour {method} {path}"
            )
            raise PermissionDeniedError(
                f"Module '{module}' non enregistré. "
                f"Publiez ses permissions via iam.registration.permissions"
            )

        # Chercher la config de l'endpoint
        ep = await self.ep_repo.get_by_path_method(
            source_id = source.id,
            path      = path,
            method    = method,
        )

        if not ep:
            # Endpoint non enregistré → bloquer par sécurité
            logger.warning(
                f"Endpoint non enregistré: {method} {path} "
                f"(module={module}). Accès bloqué."
            )
            raise PermissionDeniedError(
                f"Endpoint {method} {path} non enregistré pour le module '{module}'. "
                f"Publiez ses endpoints via iam.registration.endpoints"
            )

        # Endpoint public → accès libre
        if ep.public:
            return

        # Vérifier l'intersection permissions
        required = set(str(u) for u in (ep.permission_uuids or []))
        if not required:
            # Aucune permission configurée → accès libre
            return

        user_perms = set(user.permissions)
        if not user_perms.intersection(required):
            logger.info(
                f"Accès refusé: user={user.profil_id} "
                f"module={module} {method} {path}"
            )
            raise PermissionDeniedError(
                f"Permission insuffisante pour {method} {path}"
            )

    def _build_context_headers(self, user: CurrentUser) -> Dict[str, str]:
        """
        Construit les headers de contexte injectés par IAM Local.
        Le module métier lit ces headers pour connaître l'utilisateur.
        Les listes sont sérialisées en JSON pour compatibilité.
        """
        import json
        return {
            "X-User-Id"          : str(user.profil_id),
            "X-User-Roles"       : json.dumps(user.roles),
            "X-User-Permissions" : json.dumps(user.permissions),
            "X-User-Type"        : user.type_profil or "",
            "X-Forwarded-By"     : "iam-local-gateway",
        }

    async def _call_module(
        self,
        module  : str,
        path    : str,
        method  : str,
        body    : Optional[Dict[str, Any]],
        params  : Optional[Dict[str, Any]],
        headers : Dict[str, str],
    ) -> GatewayResponseSchema:
        """
        Fait la vraie requête HTTP vers le module métier.
        Retourne la réponse encapsulée.
        """
        base_url   = get_module_url(module)
        target_url = f"{base_url}{path}"

        logger.info(f"Gateway → {method} {target_url}")

        try:
            async with httpx.AsyncClient(
                timeout=MODULE_REQUEST_TIMEOUT
            ) as client:
                response = await client.request(
                    method  = method,
                    url     = target_url,
                    json    = body    if body   else None,
                    params  = params  if params else None,
                    headers = headers,
                )

            # Tenter de parser la réponse en JSON
            try:
                data = response.json()
            except Exception:
                data = response.text

            success = 200 <= response.status_code < 300

            logger.info(
                f"Gateway ← {method} {target_url} "
                f"status={response.status_code}"
            )

            return GatewayResponseSchema(
                success     = success,
                status_code = response.status_code,
                data        = data,
                error       = None if success else str(data),
                module      = module,
                path        = path,
                method      = method,
            )

        except httpx.ConnectError:
            logger.error(f"Module '{module}' injoignable: {target_url}")
            return GatewayResponseSchema(
                success     = False,
                status_code = 502,
                error       = f"Module '{module}' injoignable. Vérifiez qu'il est démarré.",
                module      = module,
                path        = path,
                method      = method,
            )

        except httpx.TimeoutException:
            logger.error(f"Timeout module '{module}': {target_url}")
            return GatewayResponseSchema(
                success     = False,
                status_code = 504,
                error       = f"Module '{module}' timeout après {MODULE_REQUEST_TIMEOUT}s.",
                module      = module,
                path        = path,
                method      = method,
            )

        except Exception as e:
            logger.error(f"Erreur gateway vers {module}: {e}", exc_info=True)
            return GatewayResponseSchema(
                success     = False,
                status_code = 500,
                error       = f"Erreur interne gateway: {str(e)}",
                module      = module,
                path        = path,
                method      = method,
            )

    def _is_admin(self, user: CurrentUser) -> bool:
        """Admins bypass la vérification des permissions gateway."""
        if user.is_bootstrap:
            return False
        return "iam.admin" in user.roles or user.type_profil == "systeme"
