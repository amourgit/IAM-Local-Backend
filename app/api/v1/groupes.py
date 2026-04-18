from uuid import UUID
from typing import Optional, List
from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.ext.asyncio import AsyncSession
from app.database import get_db
from app.middleware.auth import get_current_user, CurrentUser
from app.services.groupe_service import GroupeService
from app.schemas.groupe import (
    GroupeCreateSchema,
    GroupeUpdateSchema,
    AjouterRolesGroupeSchema,
    GroupeResponseSchema,
    GroupeListSchema,
)
from app.schemas.assignation import (
    AssignationGroupeCreateSchema,
    AssignationGroupeResponseSchema,
)

router = APIRouter(prefix="/groupes", tags=["IAM — Groupes"])


@router.post(
    "/",
    response_model = GroupeResponseSchema,
    status_code    = status.HTTP_201_CREATED,
    summary        = "Créer un groupe",
)
async def create_groupe(
    data : GroupeCreateSchema,
    db   : AsyncSession = Depends(get_db),
    user : CurrentUser  = Depends(get_current_user),
):
    service = GroupeService(db)
    return await service.create(data, user.profil_id)


@router.get(
    "/",
    response_model = List[GroupeListSchema],
    summary        = "Lister les groupes",
)
async def list_groupes(
    type_groupe : Optional[str] = Query(None),
    skip        : int           = Query(0,  ge=0),
    limit       : int           = Query(50, ge=1, le=200),
    db          : AsyncSession  = Depends(get_db),
    user        : CurrentUser   = Depends(get_current_user),
):
    service = GroupeService(db)
    return await service.get_all(skip=skip, limit=limit, type_groupe=type_groupe)


@router.get(
    "/{groupe_id}",
    response_model = GroupeResponseSchema,
    summary        = "Détail d'un groupe avec ses rôles",
)
async def get_groupe(
    groupe_id : UUID,
    db        : AsyncSession = Depends(get_db),
    user      : CurrentUser  = Depends(get_current_user),
):
    service = GroupeService(db)
    return await service.get_by_id(groupe_id)


@router.put(
    "/{groupe_id}",
    response_model = GroupeResponseSchema,
    summary        = "Modifier un groupe",
)
async def update_groupe(
    groupe_id : UUID,
    data      : GroupeUpdateSchema,
    db        : AsyncSession = Depends(get_db),
    user      : CurrentUser  = Depends(get_current_user),
):
    service = GroupeService(db)
    return await service.update(groupe_id, data, user.profil_id)


@router.post(
    "/{groupe_id}/roles/ajouter",
    response_model = GroupeResponseSchema,
    summary        = "Ajouter des rôles à un groupe",
)
async def ajouter_roles(
    groupe_id : UUID,
    data      : AjouterRolesGroupeSchema,
    db        : AsyncSession = Depends(get_db),
    user      : CurrentUser  = Depends(get_current_user),
):
    service = GroupeService(db)
    return await service.ajouter_roles(groupe_id, data, user.profil_id)


@router.delete(
    "/{groupe_id}/roles/{role_id}",
    response_model = GroupeResponseSchema,
    summary        = "Retirer un rôle d'un groupe",
)
async def retirer_role(
    groupe_id : UUID,
    role_id   : UUID,
    db        : AsyncSession = Depends(get_db),
    user      : CurrentUser  = Depends(get_current_user),
):
    service = GroupeService(db)
    return await service.retirer_role(groupe_id, role_id, user.profil_id)


@router.post(
    "/{groupe_id}/membres",
    response_model = AssignationGroupeResponseSchema,
    status_code    = status.HTTP_201_CREATED,
    summary        = "Ajouter un membre à un groupe",
)
async def ajouter_membre(
    groupe_id : UUID,
    data      : AssignationGroupeCreateSchema,
    db        : AsyncSession = Depends(get_db),
    user      : CurrentUser  = Depends(get_current_user),
):
    data.groupe_id = groupe_id
    service = GroupeService(db)
    return await service.ajouter_membre(data, user.profil_id)


@router.delete(
    "/{groupe_id}/membres/{assignation_id}",
    status_code = status.HTTP_204_NO_CONTENT,
    summary     = "Retirer un membre d'un groupe",
)
async def retirer_membre(
    groupe_id      : UUID,
    assignation_id : UUID,
    raison         : Optional[str] = Query(None),
    db             : AsyncSession  = Depends(get_db),
    user           : CurrentUser   = Depends(get_current_user),
):
    service = GroupeService(db)
    await service.retirer_membre(assignation_id, user.profil_id, raison)


@router.delete(
    "/{groupe_id}",
    status_code = status.HTTP_204_NO_CONTENT,
    summary     = "Supprimer un groupe",
)
async def delete_groupe(
    groupe_id : UUID,
    db        : AsyncSession = Depends(get_db),
    user      : CurrentUser  = Depends(get_current_user),
):
    service = GroupeService(db)
    await service.delete(groupe_id, user.profil_id)
