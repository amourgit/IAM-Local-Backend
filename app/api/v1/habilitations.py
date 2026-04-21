"""
Endpoints IAM — Habilitations.

Calcul et vérification des permissions effectives d'un profil.
Ces endpoints sont le cœur du système IAM pour les microservices.
"""
import logging
from uuid import UUID
from typing import Optional, List
from fastapi import APIRouter, Depends, Request, status, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.middleware.auth import get_current_user, CurrentUser
from app.services.habilitation_service import HabilitationService
from app.schemas.habilitation import (
    HabilitationsSchema,
    VerifierPermissionSchema,
    VerifierPermissionsBatchSchema,
    ResultatVerificationSchema,
    ResultatBatchSchema,
)
from app.core.exceptions import PermissionDeniedError

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/habilitations", tags=["IAM — Habilitations"])


# ══════════════════════════════════════════════════════════════
# CONSULTATION DES HABILITATIONS
# ══════════════════════════════════════════════════════════════

@router.get(
    "/moi",
    response_model = HabilitationsSchema,
    summary        = "Mes habilitations complètes",
    description    = (
        "Retourne toutes les permissions effectives du profil connecté "
        "avec leurs périmètres et leurs sources (rôle/groupe/délégation). "
        "Mis en cache Redis 15 minutes."
    ),
)
async def mes_habilitations(
    db   : AsyncSession = Depends(get_db),
    user : CurrentUser  = Depends(get_current_user),
) -> HabilitationsSchema:
    service = HabilitationService(db)
    return await service.get_habilitations(user.profil_id)


@router.get(
    "/{profil_id}",
    response_model = HabilitationsSchema,
    summary        = "Habilitations d'un profil",
    description    = (
        "Retourne toutes les permissions effectives d'un profil donné. "
        "Un profil peut consulter ses propres habilitations. "
        "Les administrateurs peuvent consulter n'importe quel profil."
    ),
)
async def habilitations_profil(
    profil_id : UUID,
    db        : AsyncSession = Depends(get_db),
    user      : CurrentUser  = Depends(get_current_user),
) -> HabilitationsSchema:
    # Un profil peut voir ses propres habilitations
    if (
        str(user.profil_id) != str(profil_id)
        and not user.has_permission("iam.habilitation.consulter")
        and not user.is_admin()
    ):
        raise PermissionDeniedError("iam.habilitation.consulter")

    service = HabilitationService(db)
    return await service.get_habilitations(profil_id)


# ══════════════════════════════════════════════════════════════
# VÉRIFICATION DE PERMISSIONS
# ══════════════════════════════════════════════════════════════

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
) -> ResultatVerificationSchema:
    service = HabilitationService(db)
    return await service.verifier_permission(
        profil_id  = user.profil_id,
        data       = data,
        request_id = getattr(request.state, "request_id", None),
    )


@router.post(
    "/{profil_id}/verifier",
    response_model = ResultatVerificationSchema,
    summary        = "Vérifier la permission d'un profil spécifique",
    description    = (
        "Permet à un service système de vérifier la permission "
        "d'un profil différent de celui du token. "
        "Réservé aux services système (iam.habilitation.verifier)."
    ),
)
async def verifier_permission_profil(
    profil_id : UUID,
    data      : VerifierPermissionSchema,
    request   : Request,
    db        : AsyncSession = Depends(get_db),
    user      : CurrentUser  = Depends(get_current_user),
) -> ResultatVerificationSchema:
    if not user.has_permission("iam.habilitation.verifier") and not user.is_admin():
        raise PermissionDeniedError("iam.habilitation.verifier")

    service = HabilitationService(db)
    return await service.verifier_permission(
        profil_id  = profil_id,
        data       = data,
        request_id = getattr(request.state, "request_id", None),
    )


@router.post(
    "/verifier-batch",
    response_model = ResultatBatchSchema,
    summary        = "Vérifier plusieurs permissions en une requête",
    description    = (
        "Optimisé pour les microservices qui ont besoin de vérifier "
        "plusieurs permissions à la fois. "
        "Mode 'any' (OR) : au moins une suffit. "
        "Mode 'all' (AND) : toutes sont nécessaires."
    ),
)
async def verifier_permissions_batch(
    data    : VerifierPermissionsBatchSchema,
    request : Request,
    db      : AsyncSession = Depends(get_db),
    user    : CurrentUser  = Depends(get_current_user),
) -> ResultatBatchSchema:
    service    = HabilitationService(db)
    request_id = getattr(request.state, "request_id", None)

    permissions_ok : List[str] = []
    permissions_ko : List[str] = []

    for perm_code in data.permissions:
        resultat = await service.verifier_permission(
            profil_id  = user.profil_id,
            data       = VerifierPermissionSchema(
                permission=perm_code,
                perimetre=data.perimetre,
            ),
            request_id = request_id,
        )
        if resultat.autorise:
            permissions_ok.append(perm_code)
        else:
            permissions_ko.append(perm_code)

    if data.mode == "all":
        autorise = len(permissions_ko) == 0
    else:  # "any"
        autorise = len(permissions_ok) > 0

    return ResultatBatchSchema(
        autorise         = autorise,
        mode             = data.mode,
        permissions_ok   = permissions_ok,
        permissions_ko   = permissions_ko,
        profil_id        = user.profil_id,
        user_id_national = None,
    )


# ══════════════════════════════════════════════════════════════
# GESTION DU CACHE
# ══════════════════════════════════════════════════════════════

@router.delete(
    "/{profil_id}/cache",
    status_code = status.HTTP_204_NO_CONTENT,
    summary     = "Invalider le cache des habilitations",
    description = (
        "Force le recalcul des habilitations au prochain accès. "
        "Appelé automatiquement après toute mutation d'habilitation. "
        "Un profil peut invalider son propre cache. "
        "Un admin peut invalider le cache de n'importe quel profil."
    ),
)
async def invalider_cache(
    profil_id : UUID,
    db        : AsyncSession = Depends(get_db),
    user      : CurrentUser  = Depends(get_current_user),
) -> None:
    if (
        str(user.profil_id) != str(profil_id)
        and not user.is_admin()
    ):
        raise PermissionDeniedError("iam.admin")

    service = HabilitationService(db)
    await service.invalider_cache(profil_id)


@router.post(
    "/admin/invalider-cache-role/{role_id}",
    status_code = status.HTTP_204_NO_CONTENT,
    summary     = "Invalider le cache de tous les profils ayant un rôle",
    description = (
        "Force le recalcul des habilitations pour tous les profils "
        "ayant ce rôle (directement ou via un groupe). "
        "Réservé aux administrateurs."
    ),
)
async def invalider_cache_role(
    role_id : UUID,
    db      : AsyncSession = Depends(get_db),
    user    : CurrentUser  = Depends(get_current_user),
) -> None:
    if not user.is_admin():
        raise PermissionDeniedError("iam.configuration.administrer")

    service = HabilitationService(db)
    await service.invalider_cache_role(role_id)


@router.post(
    "/admin/invalider-cache-groupe/{groupe_id}",
    status_code = status.HTTP_204_NO_CONTENT,
    summary     = "Invalider le cache de tous les membres d'un groupe",
    description = (
        "Force le recalcul des habilitations pour tous les membres du groupe. "
        "Réservé aux administrateurs."
    ),
)
async def invalider_cache_groupe(
    groupe_id : UUID,
    db        : AsyncSession  = Depends(get_db),
    user      : CurrentUser   = Depends(get_current_user),
) -> None:
    if not user.is_admin():
        raise PermissionDeniedError("iam.configuration.administrer")

    service = HabilitationService(db)
    await service.invalider_cache_groupe(groupe_id)
