from typing import Optional, List
from uuid import UUID
from sqlalchemy import select, and_
from sqlalchemy.orm import selectinload
from sqlalchemy.ext.asyncio import AsyncSession
from app.repositories.base import BaseRepository
from app.models.permission import Permission
from app.models.permission_source import PermissionSource


class PermissionSourceRepository(BaseRepository[PermissionSource]):

    def __init__(self, db: AsyncSession):
        super().__init__(PermissionSource, db)

    async def get_by_code(self, code: str) -> Optional[PermissionSource]:
        result = await self.db.execute(
            select(PermissionSource).where(
                and_(
                    PermissionSource.code       == code,
                    PermissionSource.is_deleted == False,
                )
            )
        )
        return result.scalar_one_or_none()

    async def get_actifs(self) -> List[PermissionSource]:
        result = await self.db.execute(
            select(PermissionSource).where(
                and_(
                    PermissionSource.actif      == True,
                    PermissionSource.is_deleted == False,
                )
            ).order_by(PermissionSource.nom)
        )
        return list(result.scalars().all())


class PermissionRepository(BaseRepository[Permission]):

    def __init__(self, db: AsyncSession):
        super().__init__(Permission, db)

    async def get_by_code(self, code: str) -> Optional[Permission]:
        result = await self.db.execute(
            select(Permission).where(
                and_(
                    Permission.code       == code,
                    Permission.is_deleted == False,
                )
            )
        )
        return result.scalar_one_or_none()

    async def get_by_domaine(self, domaine: str) -> List[Permission]:
        result = await self.db.execute(
            select(Permission).where(
                and_(
                    Permission.domaine    == domaine,
                    Permission.actif      == True,
                    Permission.is_deleted == False,
                )
            ).order_by(Permission.code)
        )
        return list(result.scalars().all())

    async def get_by_source(self, source_id: UUID) -> List[Permission]:
        result = await self.db.execute(
            select(Permission).where(
                and_(
                    Permission.source_id  == source_id,
                    Permission.is_deleted == False,
                )
            ).order_by(Permission.code)
        )
        return list(result.scalars().all())

    async def get_by_codes(self, codes: List[str]) -> List[Permission]:
        result = await self.db.execute(
            select(Permission).where(
                and_(
                    Permission.code.in_(codes),
                    Permission.actif      == True,
                    Permission.is_deleted == False,
                )
            )
        )
        return list(result.scalars().all())

    async def get_actives(self) -> List[Permission]:
        result = await self.db.execute(
            select(Permission).where(
                and_(
                    Permission.actif      == True,
                    Permission.deprecated == False,
                    Permission.is_deleted == False,
                )
            ).order_by(Permission.domaine, Permission.code)
        )
        return list(result.scalars().all())

    async def search(self, q: str) -> List[Permission]:
        result = await self.db.execute(
            select(Permission).where(
                and_(
                    Permission.is_deleted == False,
                    (
                        Permission.code.ilike(f"%{q}%")
                        | Permission.nom.ilike(f"%{q}%")
                        | Permission.domaine.ilike(f"%{q}%")
                        | Permission.ressource.ilike(f"%{q}%")
                        | Permission.action.ilike(f"%{q}%")
                    )
                )
            ).order_by(Permission.code)
        )
        return list(result.scalars().all())
