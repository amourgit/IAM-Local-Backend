from uuid import UUID
from typing import Optional, List
from datetime import datetime
from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession
from app.database import get_db
from app.middleware.auth import get_current_user, CurrentUser
from app.repositories.journal_acces import JournalAccesRepository
from app.schemas.journal import JournalAccesResponseSchema

router = APIRouter(prefix="/audit", tags=["IAM — Audit"])


@router.get(
    "/moi",
    response_model = List[JournalAccesResponseSchema],
    summary        = "Mon journal d'activité",
)
async def mon_journal(
    skip  : int          = Query(0,  ge=0),
    limit : int          = Query(50, ge=1, le=200),
    db    : AsyncSession = Depends(get_db),
    user  : CurrentUser  = Depends(get_current_user),
):
    repo  = JournalAccesRepository(db)
    items = await repo.get_by_profil(user.profil_id, skip=skip, limit=limit)
    return [JournalAccesResponseSchema.model_validate(j) for j in items]


@router.get(
    "/",
    response_model = List[JournalAccesResponseSchema],
    summary        = "Journal d'audit global",
)
async def journal_global(
    profil_id        : Optional[UUID]     = Query(None),
    user_id_national : Optional[UUID]     = Query(None),
    type_action      : Optional[str]      = Query(None),
    module           : Optional[str]      = Query(None),
    autorise         : Optional[bool]     = Query(None),
    date_debut       : Optional[datetime] = Query(None),
    date_fin         : Optional[datetime] = Query(None),
    ip_address       : Optional[str]      = Query(None),
    skip             : int                = Query(0,  ge=0),
    limit            : int                = Query(50, ge=1, le=500),
    db               : AsyncSession       = Depends(get_db),
    user             : CurrentUser        = Depends(get_current_user),
):
    repo  = JournalAccesRepository(db)
    items = await repo.search(
        profil_id=profil_id, user_id_national=user_id_national,
        type_action=type_action, module=module, autorise=autorise,
        date_debut=date_debut, date_fin=date_fin,
        ip_address=ip_address, skip=skip, limit=limit,
    )
    return [JournalAccesResponseSchema.model_validate(j) for j in items]


@router.get(
    "/profil/{profil_id}",
    response_model = List[JournalAccesResponseSchema],
    summary        = "Journal d'activité d'un profil",
)
async def journal_profil(
    profil_id : UUID,
    skip      : int          = Query(0,  ge=0),
    limit     : int          = Query(50, ge=1, le=200),
    db        : AsyncSession = Depends(get_db),
    user      : CurrentUser  = Depends(get_current_user),
):
    repo  = JournalAccesRepository(db)
    items = await repo.get_by_profil(profil_id, skip=skip, limit=limit)
    return [JournalAccesResponseSchema.model_validate(j) for j in items]
