"""
Endpoint gateway — point d'entrée unique pour toutes les requêtes
vers les modules métier.
"""

from fastapi import APIRouter, Depends, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.middleware.auth import get_current_user, CurrentUser
from app.services.gateway_service import GatewayService
from app.schemas.gateway import GatewayRequestSchema, GatewayResponseSchema

router = APIRouter(prefix="/gateway", tags=["Gateway — Routage modules"])


@router.post(
    "/forward",
    response_model = GatewayResponseSchema,
    status_code    = status.HTTP_200_OK,
    summary        = "Router une requête vers un module métier",
    description    = (
        "Point d'entrée unique du Gateway IAM Local. "
        "Le frontend encapsule toutes ses requêtes vers les modules métier ici. "
        "IAM Local vérifie les permissions puis route vers le module cible.\n\n"
        "**Flux :**\n"
        "1. Validation du token JWT\n"
        "2. Vérification des permissions sur (module + path + method)\n"
        "3. Routage vers le module métier\n"
        "4. Retour de la réponse au frontend"
    ),
)
async def forward(
    request : GatewayRequestSchema,
    db      : AsyncSession  = Depends(get_db),
    user    : CurrentUser   = Depends(get_current_user),
) -> GatewayResponseSchema:
    service = GatewayService(db)
    return await service.forward(request, user)


@router.get(
    "/modules",
    summary     = "Lister les modules connus du gateway",
    description = "Retourne la liste des modules métier enregistrés.",
)
async def list_modules(
    user: CurrentUser = Depends(get_current_user),
) -> dict:
    from app.core.module_registry import get_all_modules
    return {
        "modules": [
            {"code": code, "url": url}
            for code, url in get_all_modules().items()
        ]
    }
