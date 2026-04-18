from typing import Optional, List
from uuid import UUID
from sqlalchemy import select, and_
from sqlalchemy.orm import selectinload
from sqlalchemy.ext.asyncio import AsyncSession
from app.repositories.base import BaseRepository
from app.models.compte_local import CompteLocal
from app.models.profil_local import ProfilLocal


class CompteLocalRepository(BaseRepository[CompteLocal]):

    def __init__(self, db: AsyncSession):
        super().__init__(CompteLocal, db)

    async def get_by_user_id_national(
        self, user_id_national: UUID
    ) -> Optional[CompteLocal]:
        result = await self.db.execute(
            select(CompteLocal).where(
                and_(
                    CompteLocal.user_id_national == user_id_national,
                    CompteLocal.is_deleted       == False,
                )
            )
        )
        return result.scalar_one_or_none()

    async def get_by_email(self, email: str) -> Optional[CompteLocal]:
        result = await self.db.execute(
            select(CompteLocal).where(
                and_(
                    CompteLocal.email      == email,
                    CompteLocal.is_deleted == False,
                )
            )
        )
        return result.scalar_one_or_none()

    async def get_by_username(self, username: str) -> Optional[CompteLocal]:
        result = await self.db.execute(
            select(CompteLocal).where(
                and_(
                    CompteLocal.username   == username,
                    CompteLocal.is_deleted == False,
                )
            )
        )
        return result.scalar_one_or_none()

    async def get_by_identifiant_national(
        self, identifiant_national: str
    ) -> Optional[CompteLocal]:
        result = await self.db.execute(
            select(CompteLocal).where(
                and_(
                    CompteLocal.identifiant_national == identifiant_national,
                    CompteLocal.is_deleted           == False,
                )
            )
        )
        return result.scalar_one_or_none()

    async def get_by_statut(self, statut: str) -> List[CompteLocal]:
        result = await self.db.execute(
            select(CompteLocal).where(
                and_(
                    CompteLocal.statut     == statut,
                    CompteLocal.is_deleted == False,
                )
            ).order_by(CompteLocal.nom)
        )
        return list(result.scalars().all())

    async def get_with_profils(self, id: UUID) -> Optional[CompteLocal]:
        """Charge le compte avec tous ses profils."""
        result = await self.db.execute(
            select(CompteLocal)
            .options(selectinload(CompteLocal.profils))
            .where(
                and_(
                    CompteLocal.id         == id,
                    CompteLocal.is_deleted == False,
                )
            )
        )
        return result.scalar_one_or_none()

    async def search(self, q: str) -> List[CompteLocal]:
        result = await self.db.execute(
            select(CompteLocal).where(
                and_(
                    CompteLocal.is_deleted == False,
                    (
                        CompteLocal.nom.ilike(f"%{q}%")
                        | CompteLocal.prenom.ilike(f"%{q}%")
                        | CompteLocal.email.ilike(f"%{q}%")
                        | CompteLocal.identifiant_national.ilike(f"%{q}%")
                    )
                )
            ).order_by(CompteLocal.nom, CompteLocal.prenom)
        )
        return list(result.scalars().all())
