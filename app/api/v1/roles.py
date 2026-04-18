from uuid import UUID
from typing import Optional, List
from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.ext.asyncio import AsyncSession
from app.database import get_db
from app.middleware.auth import get_current_user, CurrentUser
from app.services.role_service import RoleService
from app.schemas.role import (
    RoleCreateSchema,
    RoleUpdateSchema,
    AjouterPermissionsSchema,
    RetirerPermissionsSchema,
    RoleResponseSchema,
    RoleListSchema,
)

router = APIRouter(prefix="/roles", tags=["IAM — Rôles"])


@router.post(
    "/",
    response_model = RoleResponseSchema,
    status_code    = status.HTTP_201_CREATED,
    summary        = "Créer un rôle",
)
async def create_role(
    data : RoleCreateSchema,
    db   : AsyncSession = Depends(get_db),
    user : CurrentUser  = Depends(get_current_user),
):
    service = RoleService(db)
    return await service.create(data, user.profil_id)


@router.get(
    "/",
    response_model = List[RoleListSchema],
    summary        = "Lister les rôles",
)
async def list_roles(
    type_role : Optional[str] = Query(None),
    q         : Optional[str] = Query(None),
    skip      : int           = Query(0,  ge=0),
    limit     : int           = Query(50, ge=1, le=200),
    db        : AsyncSession  = Depends(get_db),
    user      : CurrentUser   = Depends(get_current_user),
):
    service = RoleService(db)
    return await service.get_all(skip=skip, limit=limit, type_role=type_role, q=q)


@router.get(
    "/{role_id}",
    response_model = RoleResponseSchema,
    summary        = "Détail d'un rôle avec ses permissions",
)
async def get_role(
    role_id : UUID,
    db      : AsyncSession = Depends(get_db),
    user    : CurrentUser  = Depends(get_current_user),
):
    service = RoleService(db)
    return await service.get_by_id(role_id)


@router.put(
    "/{role_id}",
    response_model = RoleResponseSchema,
    summary        = "Modifier un rôle",
)
async def update_role(
    role_id : UUID,
    data    : RoleUpdateSchema,
    db      : AsyncSession = Depends(get_db),
    user    : CurrentUser  = Depends(get_current_user),
):
    service = RoleService(db)
    return await service.update(role_id, data, user.profil_id)


@router.post(
    "/{role_id}/permissions/ajouter",
    response_model = RoleResponseSchema,
    summary        = "Ajouter des permissions à un rôle",
)
async def ajouter_permissions(
    role_id : UUID,
    data    : AjouterPermissionsSchema,
    db      : AsyncSession = Depends(get_db),
    user    : CurrentUser  = Depends(get_current_user),
):
    service = RoleService(db)
    return await service.ajouter_permissions(role_id, data, user.profil_id)


@router.post(
    "/{role_id}/permissions/retirer",
    response_model = RoleResponseSchema,
    summary        = "Retirer des permissions d'un rôle",
)
async def retirer_permissions(
    role_id : UUID,
    data    : RetirerPermissionsSchema,
    db      : AsyncSession = Depends(get_db),
    user    : CurrentUser  = Depends(get_current_user),
):
    service = RoleService(db)
    return await service.retirer_permissions(role_id, data, user.profil_id)


@router.delete(
    "/{role_id}",
    status_code = status.HTTP_204_NO_CONTENT,
    summary     = "Supprimer un rôle",
)
async def delete_role(
    role_id : UUID,
    db      : AsyncSession = Depends(get_db),
    user    : CurrentUser  = Depends(get_current_user),
):
    service = RoleService(db)
    await service.delete(role_id, user.profil_id)
