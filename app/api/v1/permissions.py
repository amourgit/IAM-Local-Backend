from uuid import UUID
from typing import Optional, List
from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.ext.asyncio import AsyncSession
from app.database import get_db
from app.middleware.auth import get_current_user, get_current_user_optional, CurrentUser
from app.services.permission_service import PermissionService
from app.schemas.permission import (
    PermissionSourceCreateSchema,
    PermissionSourceResponseSchema,
    PermissionCreateSchema,
    PermissionUpdateSchema,
    PermissionResponseSchema,
    PermissionListSchema,
    EnregistrementPermissionsSchema,
    PermissionCustomCreateSchema,
)

router = APIRouter(prefix="/permissions", tags=["IAM — Permissions"])


@router.post(
    "/sources",
    response_model = PermissionSourceResponseSchema,
    status_code    = status.HTTP_201_CREATED,
    summary        = "Enregistrer un microservice comme source de permissions",
)
async def enregistrer_source(
    data : PermissionSourceCreateSchema,
    db   : AsyncSession  = Depends(get_db),
    user : CurrentUser   = Depends(get_current_user),
):
    service = PermissionService(db)
    return await service.enregistrer_source(data, user.profil_id)


@router.get(
    "/sources",
    response_model = List[PermissionSourceResponseSchema],
    summary        = "Lister les microservices enregistrés",
)
async def list_sources(
    db   : AsyncSession = Depends(get_db),
    user : CurrentUser  = Depends(get_current_user),
):
    service = PermissionService(db)
    return await service.get_sources()


@router.post(
    "/enregistrer",
    status_code = status.HTTP_200_OK,
    summary     = "Déclarer les permissions d'un microservice (en masse)",
)
async def enregistrement_masse(
    data : EnregistrementPermissionsSchema,
    db   : AsyncSession = Depends(get_db),
    user : Optional[CurrentUser] = Depends(get_current_user_optional),
):
    service = PermissionService(db)
    # user peut être None pour les appels internes service-to-service
    profil_id = user.profil_id if user else None
    return await service.enregistrement_masse(data, profil_id)


@router.post(
    "/",
    response_model = PermissionResponseSchema,
    status_code    = status.HTTP_201_CREATED,
    summary        = "Créer une permission manuellement",
)
async def create_permission(
    data : PermissionCreateSchema,
    db   : AsyncSession = Depends(get_db),
    user : CurrentUser  = Depends(get_current_user),
):
    service = PermissionService(db)
    return await service.create(data, user.profil_id)


@router.post(
    "/custom",
    response_model = PermissionResponseSchema,
    status_code    = status.HTTP_201_CREATED,
    summary        = "Créer une permission custom",
)
async def create_custom_permission(
    data : PermissionCustomCreateSchema,
    db   : AsyncSession = Depends(get_db),
    user : CurrentUser  = Depends(get_current_user),
):
    service = PermissionService(db)
    perm = await service.create_custom_permission(data, user.profil_id)
    return PermissionResponseSchema.model_validate(perm.model_dump())


@router.get(
    "/",
    response_model = List[PermissionListSchema],
    summary        = "Lister les permissions",
)
async def list_permissions(
    domaine : Optional[str] = Query(None),
    q       : Optional[str] = Query(None),
    skip    : int           = Query(0,   ge=0),
    limit   : int           = Query(100, ge=1, le=500),
    db      : AsyncSession  = Depends(get_db),
    user    : CurrentUser   = Depends(get_current_user),
):
    service = PermissionService(db)
    return await service.get_all(skip=skip, limit=limit, domaine=domaine, q=q)


@router.get(
    "/{permission_id}",
    response_model = PermissionResponseSchema,
    summary        = "Détail d'une permission",
)
async def get_permission(
    permission_id : UUID,
    db            : AsyncSession = Depends(get_db),
    user          : CurrentUser  = Depends(get_current_user),
):
    service = PermissionService(db)
    return await service.get_by_id(permission_id)


@router.put(
    "/{permission_id}",
    response_model = PermissionResponseSchema,
    summary        = "Modifier une permission",
)
async def update_permission(
    permission_id : UUID,
    data          : PermissionUpdateSchema,
    db            : AsyncSession = Depends(get_db),
    user          : CurrentUser  = Depends(get_current_user),
):
    service = PermissionService(db)
    return await service.update(permission_id, data, user.profil_id)
