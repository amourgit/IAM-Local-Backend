import logging
from fastapi import Request, Response
from fastapi.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware
import httpx

from app.services.endpoint_permission_service import EndpointPermissionService
from app.middleware.auth import get_current_user
from app.database import get_db
from app.utils.gateway_helpers import (
    get_module_url,
    extract_module_from_path,
    is_internal_path,
)
from app.repositories.permission import PermissionSourceRepository

logger = logging.getLogger(__name__)


class GatewayMiddleware(BaseHTTPMiddleware):
    """
    Middleware principal du gateway IAM Local.

    Étapes:
    1. Vérifier si chemin interne (IAM Local) => laisser passer
    2. Authentifier l'utilisateur (token JWT)
    3. Extraire le module cible du chemin
    4. Récupérer la configuration d'endpoint (permissions requises)
    5. Vérifier que l'utilisateur possède l'une des permissions
    6. Proxifier la requête vers le module
    7. Injecter X-User-Context en header
    """

    async def dispatch(self, request: Request, call_next):
        # étape 1 : chemins internes
        if is_internal_path(request.url.path):
            return await call_next(request)

        # étape 2 : authentification
        try:
            user = await get_current_user(request)
        except Exception as e:
            logger.debug(f"auth failure: {e}")
            return JSONResponse(status_code=401, content={"detail": str(e)})

        # étape 3 : extraire module
        module = extract_module_from_path(request.url.path)
        if not module:
            return JSONResponse(status_code=400, content={"detail": "Invalid path format"})

        module_url = get_module_url(module)
        if not module_url:
            logger.warning(f"Unknown module route for {module}")
            return JSONResponse(status_code=502, content={"detail": "Service unavailable"})

        # étape 4 : récupérer config endpoint
        try:
            async with get_db() as db:
                src_repo = PermissionSourceRepository(db)
                source = await src_repo.get_by_code(module)
                if not source:
                    logger.warning(f"no permission source record for module {module}")
                    return JSONResponse(status_code=502, content={"detail": "Unknown service"})

                svc = EndpointPermissionService(db)
                ep = await svc.get_for_request(source.id, request.url.path, request.method)
        except Exception as e:
            logger.error(f"error loading endpoint permission: {e}")
            return JSONResponse(status_code=500, content={"detail": "Internal error"})

        # étape 5 : vérifier permission
        if not ep:
            logger.warning(f"no endpoint permission entry for {request.url.path}")
            return JSONResponse(status_code=403, content={"detail": "Endpoint not registered"})

        if not ep.public:
            needed = set(ep.permission_uuids)
            user_perms = set(user.permissions)
            if not user_perms.intersection(needed) and not user.is_admin():
                logger.info(f"permission denied for {user.profil_id} on {request.url.path}")
                return JSONResponse(status_code=403, content={"detail": "Permission denied"})

        # étape 6 : proxifier requête
        path_parts = request.url.path.lstrip("/").split("/")
        target_path = "/" + "/".join(path_parts[:2] + path_parts[3:])
        target = module_url + target_path

        try:
            async with httpx.AsyncClient() as client:
                headers = {k: v for k, v in request.headers.items() if k.lower() != "host"}
                # étape 7 : injecter contexte
                headers["x-user-id"] = str(user.profil_id)
                headers["x-user-permissions"] = ",".join(map(str, user.permissions))

                body = await request.body()
                resp = await client.request(
                    request.method,
                    target,
                    headers=headers,
                    content=body,
                    params=dict(request.query_params),
                )
                return Response(
                    content=resp.content,
                    status_code=resp.status_code,
                    headers=dict(resp.headers)
                )
        except httpx.RequestError as e:
            logger.error(f"proxy error: {e}")
            return JSONResponse(status_code=502, content={"detail": "Upstream error"})
