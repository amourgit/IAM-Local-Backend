from typing import Optional, List
from uuid import UUID
from datetime import datetime
from sqlalchemy import select, and_, desc
from sqlalchemy.ext.asyncio import AsyncSession
from app.models.journal_acces import JournalAcces


class JournalAccesRepository:

    def __init__(self, db: AsyncSession):
        self.db = db

    async def create(self, data: dict) -> JournalAcces:
        entree = JournalAcces(**data)
        self.db.add(entree)
        await self.db.flush()
        return entree

    async def get_by_profil(
        self,
        profil_id  : UUID,
        skip       : int = 0,
        limit      : int = 50,
    ) -> List[JournalAcces]:
        result = await self.db.execute(
            select(JournalAcces)
            .where(JournalAcces.profil_id == profil_id)
            .order_by(desc(JournalAcces.timestamp))
            .offset(skip)
            .limit(limit)
        )
        return list(result.scalars().all())

    async def search(
        self,
        profil_id        : Optional[UUID]     = None,
        user_id_national : Optional[UUID]     = None,
        type_action      : Optional[str]      = None,
        module           : Optional[str]      = None,
        autorise         : Optional[bool]     = None,
        date_debut       : Optional[datetime] = None,
        date_fin         : Optional[datetime] = None,
        ip_address       : Optional[str]      = None,
        skip             : int                = 0,
        limit            : int                = 50,
    ) -> List[JournalAcces]:

        conditions = []

        if profil_id:
            conditions.append(JournalAcces.profil_id == profil_id)
        if user_id_national:
            conditions.append(
                JournalAcces.user_id_national == user_id_national
            )
        if type_action:
            conditions.append(JournalAcces.type_action == type_action)
        if module:
            conditions.append(JournalAcces.module == module)
        if autorise is not None:
            conditions.append(JournalAcces.autorise == autorise)
        if date_debut:
            conditions.append(JournalAcces.timestamp >= date_debut)
        if date_fin:
            conditions.append(JournalAcces.timestamp <= date_fin)
        if ip_address:
            conditions.append(JournalAcces.ip_address == ip_address)

        query = select(JournalAcces).order_by(
            desc(JournalAcces.timestamp)
        )
        if conditions:
            query = query.where(and_(*conditions))

        query = query.offset(skip).limit(limit)
        result = await self.db.execute(query)
        return list(result.scalars().all())

    async def count_echecs_auth(
        self,
        user_id_national : UUID,
        depuis           : datetime,
    ) -> int:
        from sqlalchemy import func
        result = await self.db.execute(
            select(func.count()).select_from(JournalAcces).where(
                and_(
                    JournalAcces.user_id_national == user_id_national,
                    JournalAcces.type_action      == "echec_auth",
                    JournalAcces.timestamp        >= depuis,
                )
            )
        )
        return result.scalar_one() or 0
