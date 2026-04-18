from typing import Optional, List
from uuid import UUID
from datetime import datetime, timezone
from sqlalchemy import select, and_
from sqlalchemy.orm import selectinload
from sqlalchemy.ext.asyncio import AsyncSession
from app.repositories.base import BaseRepository
from app.models.assignation_groupe import AssignationGroupe
from app.models.groupe import Groupe


class AssignationGroupeRepository(BaseRepository[AssignationGroupe]):

    def __init__(self, db: AsyncSession):
        super().__init__(AssignationGroupe, db)

    async def get_by_profil(
        self,
        profil_id        : UUID,
        actives_seulement: bool = True,
    ) -> List[AssignationGroupe]:
        conditions = [
            AssignationGroupe.profil_id  == profil_id,
            AssignationGroupe.is_deleted == False,
        ]
        if actives_seulement:
            now = datetime.now(timezone.utc)
            conditions.append(AssignationGroupe.statut == "active")
            conditions.append(
                (AssignationGroupe.date_fin == None)
                | (AssignationGroupe.date_fin >= now)
            )

        result = await self.db.execute(
            select(AssignationGroupe)
            .options(selectinload(AssignationGroupe.groupe))
            .where(and_(*conditions))
        )
        return list(result.scalars().all())

    async def get_by_groupe(
        self, groupe_id: UUID
    ) -> List[AssignationGroupe]:
        result = await self.db.execute(
            select(AssignationGroupe).where(
                and_(
                    AssignationGroupe.groupe_id  == groupe_id,
                    AssignationGroupe.statut     == "active",
                    AssignationGroupe.is_deleted == False,
                )
            )
        )
        return list(result.scalars().all())

    async def get_assignation_existante(
        self,
        profil_id : UUID,
        groupe_id : UUID,
    ) -> Optional[AssignationGroupe]:
        result = await self.db.execute(
            select(AssignationGroupe).where(
                and_(
                    AssignationGroupe.profil_id  == profil_id,
                    AssignationGroupe.groupe_id  == groupe_id,
                    AssignationGroupe.statut     == "active",
                    AssignationGroupe.is_deleted == False,
                )
            )
        )
        return result.scalar_one_or_none()

    async def retirer(
        self,
        assignation_id : UUID,
        retire_par     : UUID,
        raison         : Optional[str] = None,
    ) -> Optional[AssignationGroupe]:
        assignation = await self.get_by_id(assignation_id)
        if not assignation:
            return None
        assignation.statut      = "revoquee"
        assignation.retire_par  = retire_par
        assignation.date_retrait = datetime.now(timezone.utc)
        assignation.raison      = raison
        self.db.add(assignation)
        await self.db.flush()
        return assignation
