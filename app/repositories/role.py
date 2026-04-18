from typing import Optional, List
from uuid import UUID
from sqlalchemy import select, and_, delete
from sqlalchemy.orm import selectinload
from sqlalchemy.ext.asyncio import AsyncSession
from app.repositories.base import BaseRepository
from app.models.role import Role, RolePermission, role_permissions_table
from app.models.permission import Permission


class RoleRepository(BaseRepository[Role]):

    def __init__(self, db: AsyncSession):
        super().__init__(Role, db)

    async def get_by_id_with_permissions(
        self, id: UUID
    ) -> Optional[Role]:
        result = await self.db.execute(
            select(Role)
            .options(selectinload(Role.permissions))
            .where(
                and_(Role.id == id, Role.is_deleted == False)
            )
        )
        return result.scalar_one_or_none()

    async def get_by_code(self, code: str) -> Optional[Role]:
        result = await self.db.execute(
            select(Role).where(
                and_(
                    Role.code       == code,
                    Role.is_deleted == False,
                )
            )
        )
        return result.scalar_one_or_none()

    async def get_by_type(self, type_role: str) -> List[Role]:
        result = await self.db.execute(
            select(Role).where(
                and_(
                    Role.type_role  == type_role,
                    Role.actif      == True,
                    Role.is_deleted == False,
                )
            ).order_by(Role.nom)
        )
        return list(result.scalars().all())

    async def get_actifs(self) -> List[Role]:
        result = await self.db.execute(
            select(Role).where(
                and_(
                    Role.actif      == True,
                    Role.is_deleted == False,
                )
            ).order_by(Role.nom)
        )
        return list(result.scalars().all())

    async def ajouter_permissions(
        self,
        role_id         : UUID,
        permissions_ids : List[UUID],
        ajoute_par      : UUID,
        raison          : Optional[str] = None,
    ) -> None:
        """Ajoute des permissions à un rôle."""
        for perm_id in permissions_ids:
            # Vérifier si l'association existe déjà
            existing = await self.db.execute(
                select(RolePermission).where(
                    and_(
                        RolePermission.role_id       == role_id,
                        RolePermission.permission_id == perm_id,
                        RolePermission.is_deleted    == False,
                    )
                )
            )
            if not existing.scalar_one_or_none():
                detail = RolePermission(
                    role_id       = role_id,
                    permission_id = perm_id,
                    ajoute_par    = ajoute_par,
                    raison        = raison,
                )
                self.db.add(detail)
        await self.db.flush()

    async def retirer_permissions(
        self,
        role_id         : UUID,
        permissions_ids : List[UUID],
        retire_par      : UUID,
    ) -> None:
        from sqlalchemy import delete as sa_delete
        from datetime import datetime
        for perm_id in permissions_ids:
            # Supprimer de la table de jonction principale
            await self.db.execute(
                sa_delete(role_permissions_table).where(
                    and_(
                        role_permissions_table.c.role_id       == role_id,
                        role_permissions_table.c.permission_id == perm_id,
                    )
                )
            )
            # Soft delete dans role_permission_details
            result = await self.db.execute(
                select(RolePermission).where(
                    and_(
                        RolePermission.role_id       == role_id,
                        RolePermission.permission_id == perm_id,
                        RolePermission.is_deleted    == False,
                    )
                )
            )
            detail = result.scalar_one_or_none()
            if detail:
                detail.is_deleted = True
                detail.deleted_at = datetime.utcnow()
                detail.deleted_by = retire_par

        await self.db.flush()

    async def search(self, q: str) -> List[Role]:
        result = await self.db.execute(
            select(Role).where(
                and_(
                    Role.is_deleted == False,
                    (
                        Role.code.ilike(f"%{q}%")
                        | Role.nom.ilike(f"%{q}%")
                    )
                )
            ).order_by(Role.nom)
        )
        return list(result.scalars().all())


    async def ajouter_permissions(
        self,
        role_id         : UUID,
        permissions_ids : List[UUID],
        ajoute_par      : UUID,
        raison          : Optional[str] = None,
    ) -> None:
        from sqlalchemy import insert
        for perm_id in permissions_ids:
            # Vérifier si déjà dans role_permissions (table de jonction)
            existing = await self.db.execute(
                select(role_permissions_table).where(
                    and_(
                        role_permissions_table.c.role_id       == role_id,
                        role_permissions_table.c.permission_id == perm_id,
                    )
                )
            )
            if not existing.scalar_one_or_none():
                # Insérer dans la table de jonction principale
                await self.db.execute(
                    insert(role_permissions_table).values(
                        role_id       = role_id,
                        permission_id = perm_id,
                    )
                )

            # Insérer dans role_permission_details (métadonnées)
            existing_detail = await self.db.execute(
                select(RolePermission).where(
                    and_(
                        RolePermission.role_id       == role_id,
                        RolePermission.permission_id == perm_id,
                        RolePermission.is_deleted    == False,
                    )
                )
            )
            if not existing_detail.scalar_one_or_none():
                detail = RolePermission(
                    role_id       = role_id,
                    permission_id = perm_id,
                    ajoute_par    = ajoute_par,
                    raison        = raison,
                )
                self.db.add(detail)

        await self.db.flush()