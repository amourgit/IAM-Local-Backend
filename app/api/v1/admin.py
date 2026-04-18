from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession
from typing import List, Optional
from uuid import UUID
from app.database import get_db
from app.middleware.auth import get_current_user, CurrentUser
from app.services.endpoint_permission_service import EndpointPermissionService
from app.schemas.endpoint_schemas import (
    EndpointPermissionResponseSchema,
    EndpointPermissionDetailSchema,
)
from app.repositories.permission import PermissionSourceRepository

router = APIRouter(prefix="/admin", tags=["IAM — Admin"])


@router.get(
    "/endpoints",
    summary = "Lister tous les endpoints de tous les modules avec permissions",
)
async def admin_list_all_endpoints(
    module : Optional[str] = Query(None),
    db     : AsyncSession  = Depends(get_db),
    user   : CurrentUser   = Depends(get_current_user),
):
    from app.repositories.endpoint_permission import EndpointPermissionRepository
    repo = EndpointPermissionRepository(db)
    rows = await repo.get_all_with_permissions()

    # Filtrer par module si demandé
    if module:
        rows = [r for r in rows if r["source_code"] == module]

    # Grouper par source
    result = {}
    for r in rows:
        src = r["source_code"]
        if src not in result:
            result[src] = {
                "source_nom" : r["source_nom"],
                "endpoints"  : []
            }
        result[src]["endpoints"].append({
            "id"              : str(r["id"]),
            "path"            : r["path"],
            "method"          : r["method"],
            "permission_codes": r["permission_codes"],
            "permission_uuids": [str(u) for u in (r["permission_uuids"] or [])],
            "public"          : r["public"],
            "description"     : r["description"],
        })

    return result

@router.get(
    "/endpoints/by-module/{module_code}",
    response_model = List[EndpointPermissionResponseSchema],
    summary        = "Lister les endpoints d'un module spécifique",
)
async def admin_list_module_endpoints(
    module_code : str,
    db          : AsyncSession = Depends(get_db),
    user        : CurrentUser  = Depends(get_current_user),
):
    src_repo = PermissionSourceRepository(db)
    source   = await src_repo.get_by_code(module_code)
    if not source:
        from app.core.exceptions import NotFoundError
        raise NotFoundError("Module", module_code)
    svc = EndpointPermissionService(db)
    return await svc.list_by_source(source.id)
