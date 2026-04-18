from typing import Optional, List
from uuid import UUID
from datetime import datetime, timezone
from sqlalchemy import select, and_
from sqlalchemy.orm import selectinload
from sqlalchemy.ext.asyncio import AsyncSession
from app.repositories.base import BaseRepository
from app.models.assignation_role import AssignationRole
from app.models.role import Role


class AssignationRoleRepository(BaseRepository[AssignationRole]):

    def __init__(self, db: AsyncSession):
        super().__init__(AssignationRole, db)

    async def get_by_profil(
        self,
        profil_id        : UUID,
        actives_seulement: bool = True,
    ) -> List[AssignationRole]:
        conditions = [
            AssignationRole.profil_id  == profil_id,
            AssignationRole.is_deleted == False,
        ]
        if actives_seulement:
            now = datetime.now(timezone.utc)
            conditions.append(AssignationRole.statut == "active")
            conditions.append(
                (AssignationRole.date_fin == None)
                | (AssignationRole.date_fin >= now)
            )

        result = await self.db.execute(
            select(AssignationRole)
            .options(selectinload(AssignationRole.role))
            .where(and_(*conditions))
        )
        return list(result.scalars().all())

    async def get_by_role(
        self, role_id: UUID
    ) -> List[AssignationRole]:
        result = await self.db.execute(
            select(AssignationRole).where(
                and_(
                    AssignationRole.role_id    == role_id,
                    AssignationRole.statut     == "active",
                    AssignationRole.is_deleted == False,
                )
            )
        )
        return list(result.scalars().all())

    async def get_assignation_existante(
        self,
        profil_id : UUID,
        role_id   : UUID,
    ) -> Optional[AssignationRole]:
        result = await self.db.execute(
            select(AssignationRole).where(
                and_(
                    AssignationRole.profil_id  == profil_id,
                    AssignationRole.role_id    == role_id,
                    AssignationRole.statut     == "active",
                    AssignationRole.is_deleted == False,
                )
            )
        )
        return result.scalar_one_or_none()

    async def revoquer(
        self,
        assignation_id    : UUID,
        revoque_par       : UUID,
        raison_revocation : str,
    ) -> Optional[AssignationRole]:
        assignation = await self.get_by_id(assignation_id)
        if not assignation:
            return None
        assignation.statut            = "revoquee"
        assignation.revoque_par       = revoque_par
        assignation.date_revocation   = datetime.now(timezone.utc)
        assignation.raison_revocation = raison_revocation
        self.db.add(assignation)
        await self.db.flush()
        return assignation
