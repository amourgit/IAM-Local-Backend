from fastapi import APIRouter

from app.api.v1.permissions     import router as permissions_router
from app.api.v1.roles           import router as roles_router
from app.api.v1.groupes         import router as groupes_router
from app.api.v1.comptes         import router as comptes_router
from app.api.v1.profils         import router as profils_router
from app.api.v1.habilitations   import router as habilitations_router
from app.api.v1.audit           import router as audit_router
from app.api.v1.endpoints       import router as endpoints_router
from app.api.v1.admin           import router as admin_router
from app.api.v1.token_endpoints import router as token_router
from app.api.v1.token_config    import router as token_config_router
from app.api.v1.gateway         import router as gateway_router

router = APIRouter()

router.include_router(permissions_router)
router.include_router(roles_router)
router.include_router(groupes_router)
router.include_router(comptes_router)   # ← Comptes Locaux
router.include_router(profils_router)
router.include_router(habilitations_router)
router.include_router(audit_router)
router.include_router(endpoints_router)
router.include_router(admin_router)
router.include_router(token_router)
router.include_router(token_config_router)
router.include_router(gateway_router)
