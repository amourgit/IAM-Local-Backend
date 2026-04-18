from typing import Optional, List
from uuid import UUID
from sqlalchemy import select, and_
from sqlalchemy.orm import selectinload
from sqlalchemy.ext.asyncio import AsyncSession
from app.repositories.base import BaseRepository
from app.models.groupe import Groupe, GroupeRole


class GroupeRepository(BaseRepository[Groupe]):

    def __init__(self, db: AsyncSession):
        super().__init__(Groupe, db)

    async def get_by_id_with_roles(
        self, id: UUID
    ) -> Optional[Groupe]:
        result = await self.db.execute(
            select(Groupe)
            .options(
                selectinload(Groupe.roles)
                .selectinload(GroupeRole.role)
            )
            .where(
                and_(Groupe.id == id, Groupe.is_deleted == False)
            )
        )
        return result.scalar_one_or_none()

    async def get_by_code(self, code: str) -> Optional[Groupe]:
        result = await self.db.execute(
            select(Groupe).where(
                and_(
                    Groupe.code       == code,
                    Groupe.is_deleted == False,
                )
            )
        )
        return result.scalar_one_or_none()

    async def get_by_type(self, type_groupe: str) -> List[Groupe]:
        result = await self.db.execute(
            select(Groupe).where(
                and_(
                    Groupe.type_groupe == type_groupe,
                    Groupe.actif       == True,
                    Groupe.is_deleted  == False,
                )
            ).order_by(Groupe.nom)
        )
        return list(result.scalars().all())

    async def get_actifs(self) -> List[Groupe]:
        result = await self.db.execute(
            select(Groupe).where(
                and_(
                    Groupe.actif      == True,
                    Groupe.is_deleted == False,
                )
            ).order_by(Groupe.nom)
        )
        return list(result.scalars().all())

    async def ajouter_role(
        self,
        groupe_id  : UUID,
        role_id    : UUID,
        perimetre  : Optional[dict],
        ajoute_par : UUID,
        raison     : Optional[str] = None,
    ) -> GroupeRole:
        existing = await self.db.execute(
            select(GroupeRole).where(
                and_(
                    GroupeRole.groupe_id  == groupe_id,
                    GroupeRole.role_id    == role_id,
                    GroupeRole.is_deleted == False,
                )
            )
        )
        if existing.scalar_one_or_none():
            return

        groupe_role = GroupeRole(
            groupe_id  = groupe_id,
            role_id    = role_id,
            perimetre  = perimetre,
            ajoute_par = ajoute_par,
            raison     = raison,
        )
        self.db.add(groupe_role)
        await self.db.flush()
        return groupe_role

    async def retirer_role(
        self,
        groupe_id  : UUID,
        role_id    : UUID,
        retire_par : UUID,
    ) -> None:
        from datetime import datetime
        result = await self.db.execute(
            select(GroupeRole).where(
                and_(
                    GroupeRole.groupe_id  == groupe_id,
                    GroupeRole.role_id    == role_id,
                    GroupeRole.is_deleted == False,
                )
            )
        )
        groupe_role = result.scalar_one_or_none()
        if groupe_role:
            groupe_role.is_deleted = True
            groupe_role.deleted_at = datetime.utcnow()
            groupe_role.deleted_by = retire_par
            await self.db.flush()

