from sqlalchemy import select, delete
from sqlalchemy.ext.asyncio import AsyncSession
from typing import List, Optional
from uuid import UUID

from app.models import EndpointPermission
from app.repositories.base import BaseRepository


class EndpointPermissionRepository(BaseRepository):
    def __init__(self, db: AsyncSession):
        super().__init__(EndpointPermission, db)

    async def get_by_source(self, source_id: UUID) -> List[EndpointPermission]:
        stmt = select(self.model).where(self.model.source_id == source_id)
        result = await self.db.execute(stmt)
        return result.scalars().all()

    async def get_by_path_method(
        self, source_id: UUID, path: str, method: str
    ) -> Optional[EndpointPermission]:
        stmt = select(self.model).where(
            self.model.source_id == source_id,
            self.model.path      == path,
            self.model.method    == method.upper(),
        )
        result = await self.db.execute(stmt)
        return result.scalar_one_or_none()

    async def get_by_path_method_any_source(
        self, path: str, method: str
    ) -> Optional[EndpointPermission]:
        """
        Cherche un endpoint par path + method sans filtrer par source.
        Utilisé par le PermissionMiddleware.
        Retourne le premier résultat actif trouvé.
        """
        stmt = select(self.model).where(
            self.model.path   == path,
            self.model.method == method.upper(),
            self.model.actif  == True,
        ).limit(1)
        result = await self.db.execute(stmt)
        return result.scalar_one_or_none()

    async def delete_by_source(self, source_id: UUID) -> None:
        stmt = delete(self.model).where(self.model.source_id == source_id)
        await self.db.execute(stmt)

    async def replace_for_source(
        self, source_id: UUID, endpoints: List[dict]
    ) -> List[EndpointPermission]:
        await self.delete_by_source(source_id)
        objs = [self.model(**e, source_id=source_id) for e in endpoints]
        self.db.add_all(objs)
        await self.db.flush()
        # Rafraîchir chaque objet pour avoir les champs auto-générés
        for obj in objs:
            await self.db.refresh(obj)
        return objs

    async def get_all_with_permissions(self) -> List[dict]:
        """Retourne tous les endpoints avec codes de permissions résolus."""
        from sqlalchemy import text
        result = await self.db.execute(text("""
            SELECT
                ep.id,
                ep.source_id,
                ps.code        AS source_code,
                ps.nom         AS source_nom,
                ep.path,
                ep.method,
                ep.permission_uuids,
                ep.description,
                ep.public,
                ep.actif,
                ep.created_at,
                ep.updated_at,
                COALESCE(
                    ARRAY(
                        SELECT p.code
                        FROM permissions p
                        WHERE p.id = ANY(ep.permission_uuids)
                        AND p.is_deleted = false
                        ORDER BY p.code
                    ),
                    ARRAY[]::VARCHAR[]
                ) AS permission_codes
            FROM endpoint_permissions ep
            JOIN permission_sources ps ON ps.id = ep.source_id
            WHERE ep.is_deleted = false
            AND ep.actif = true
            ORDER BY ps.code, ep.path, ep.method
        """))
        rows = result.mappings().all()
        return [dict(r) for r in rows]
