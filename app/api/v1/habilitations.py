from uuid import UUID
from typing import Optional
from fastapi import APIRouter, Depends, Request, status
from sqlalchemy.ext.asyncio import AsyncSession
from app.database import get_db
from app.middleware.auth import get_current_user, CurrentUser
from app.services.habilitation_service import HabilitationService
from app.schemas.habilitation import (
    HabilitationsSchema,
    VerifierPermissionSchema,
    ResultatVerificationSchema,
)

router = APIRouter(prefix="/habilitations", tags=["IAM — Habilitations"])


@router.get(
    "/moi",
    response_model = HabilitationsSchema,
    summary        = "Mes habilitations complètes",
    description    = (
        "Retourne toutes les permissions effectives "
        "de l'utilisateur connecté avec leurs périmètres. "
        "Mis en cache 15 minutes."
    ),
)
async def mes_habilitations(
    db   : AsyncSession = Depends(get_db),
    user : CurrentUser  = Depends(get_current_user),
):
    service = HabilitationService(db)
    return await service.get_habilitations(user.profil_id)


@router.get(
    "/{profil_id}",
    response_model = HabilitationsSchema,
    summary        = "Habilitations d'un profil",
    description    = (
        "Retourne toutes les permissions effectives "
        "d'un profil donné. "
        "Réservé aux administrateurs IAM."
    ),
)
async def habilitations_profil(
    profil_id : UUID,
    db        : AsyncSession = Depends(get_db),
    user      : CurrentUser  = Depends(get_current_user),
):
    from app.middleware.auth import require_permission
    from app.core.exceptions import PermissionDeniedError

    if (
        str(user.profil_id) != str(profil_id)
        and not user.has_permission("iam.habilitation.consulter")
        and not user.is_admin()
    ):
        raise PermissionDeniedError("iam.habilitation.consulter")

    service = HabilitationService(db)
    return await service.get_habilitations(profil_id)


@router.post(
    "/verifier",
    response_model = ResultatVerificationSchema,
    summary        = "Vérifier une permission",
    description    = (
        "Endpoint central appelé par tous les microservices. "
        "Vérifie si le porteur du token a une permission "
        "donnée sur un périmètre donné. "
        "Chaque appel est tracé dans le journal d'audit."
    ),
)
async def verifier_permission(
    data    : VerifierPermissionSchema,
    request : Request,
    db      : AsyncSession = Depends(get_db),
    user    : CurrentUser  = Depends(get_current_user),
):
    service = HabilitationService(db)
    return await service.verifier_permission(
        profil_id  = user.profil_id,
        data       = data,
        request_id = getattr(request.state, "request_id", None),
    )


@router.post(
    "/{profil_id}/verifier",
    response_model = ResultatVerificationSchema,
    summary        = "Vérifier une permission pour un profil spécifique",
    description    = (
        "Permet à un microservice de vérifier "
        "la permission d'un autre profil que celui du token. "
        "Réservé aux services systèmes."
    ),
)
async def verifier_permission_profil(
    profil_id : UUID,
    data      : VerifierPermissionSchema,
    request   : Request,
    db        : AsyncSession = Depends(get_db),
    user      : CurrentUser  = Depends(get_current_user),
):
    from app.core.exceptions import PermissionDeniedError

    if not user.has_permission("iam.habilitation.verifier_autre") and not user.is_admin():
        raise PermissionDeniedError("iam.habilitation.verifier_autre")

    service = HabilitationService(db)
    return await service.verifier_permission(
        profil_id  = profil_id,
        data       = data,
        request_id = getattr(request.state, "request_id", None),
    )


@router.delete(
    "/{profil_id}/cache",
    status_code = status.HTTP_204_NO_CONTENT,
    summary     = "Invalider le cache des habilitations d'un profil",
    description = (
        "Force le recalcul des habilitations au prochain accès. "
        "Appelé automatiquement après toute modification d'habilitation."
    ),
)
async def invalider_cache(
    profil_id : UUID,
    db        : AsyncSession = Depends(get_db),
    user      : CurrentUser  = Depends(get_current_user),
):
    from app.core.exceptions import PermissionDeniedError

    if (
        str(user.profil_id) != str(profil_id)
        and not user.is_admin()
    ):
        raise PermissionDeniedError("iam.admin")

    service = HabilitationService(db)
    await service.invalider_cache(profil_id)
