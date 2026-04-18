from fastapi import APIRouter, Depends, status
from sqlalchemy.ext.asyncio import AsyncSession
from typing import List, Optional
from app.database import get_db
from app.middleware.auth import get_current_user, get_current_user_optional, CurrentUser
from app.services.endpoint_permission_service import EndpointPermissionService
from app.schemas.endpoint_schemas import (
    EnregistrementEndpointsSchema,
    EndpointPermissionResponseSchema,
)

router = APIRouter(prefix="/endpoints", tags=["IAM — Endpoints"])


@router.post(
    "/register",
    response_model = List[EndpointPermissionResponseSchema],
    status_code    = status.HTTP_200_OK,
    summary        = "Enregistrer ou mettre à jour les endpoints d'un module",
)
async def register_endpoints(
    data : EnregistrementEndpointsSchema,
    db   : AsyncSession = Depends(get_db),
    user : Optional[CurrentUser] = Depends(get_current_user_optional),
):
    service = EndpointPermissionService(db)
    # user peut être None pour les appels internes service-to-service
    profil_id = user.profil_id if user else None
    return await service.register_endpoints(data, profil_id)


@router.get(
    "/",
    response_model = List[EndpointPermissionResponseSchema],
    summary        = "Lister les endpoints enregistrés",
)
async def list_endpoints(
    db   : AsyncSession = Depends(get_db),
    user : CurrentUser  = Depends(get_current_user),
):
    service = EndpointPermissionService(db)
    return await service.list_by_source(user.profil_id)
