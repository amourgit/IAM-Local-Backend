from typing import TypeVar, Generic, Type, Optional, List, Any
from uuid import UUID
from datetime import datetime
from sqlalchemy import select, func, and_
from sqlalchemy.ext.asyncio import AsyncSession
from app.models.base import BaseModel

ModelType = TypeVar("ModelType", bound=BaseModel)


class BaseRepository(Generic[ModelType]):

    def __init__(self, model: Type[ModelType], db: AsyncSession):
        self.model = model
        self.db    = db

    async def get_by_id(self, id: UUID) -> Optional[ModelType]:
        result = await self.db.execute(
            select(self.model).where(
                and_(
                    self.model.id         == id,
                    self.model.is_deleted == False,
                )
            )
        )
        return result.scalar_one_or_none()

    async def get_all(
        self,
        skip    : int = 0,
        limit   : int = 50,
        filters : Optional[List[Any]] = None,
    ) -> List[ModelType]:
        query = select(self.model).where(self.model.is_deleted == False)
        if filters:
            query = query.where(and_(*filters))
        query = query.offset(skip).limit(limit)
        result = await self.db.execute(query)
        return list(result.scalars().all())

    async def count(
        self,
        filters: Optional[List[Any]] = None,
    ) -> int:
        query = select(func.count()).select_from(self.model).where(
            self.model.is_deleted == False
        )
        if filters:
            query = query.where(and_(*filters))
        result = await self.db.execute(query)
        return result.scalar_one()

    async def create(self, data: dict) -> ModelType:
        instance = self.model(**data)
        self.db.add(instance)
        await self.db.flush()
        await self.db.refresh(instance)
        return instance

    async def update(
        self,
        instance : ModelType,
        data     : dict,
    ) -> ModelType:
        for field, value in data.items():
            # ✅ CORRIGÉ : on retire "and value is not None" pour permettre
            # d'effacer un champ (ex: raison_suspension=None à la réactivation)
            if hasattr(instance, field):
                setattr(instance, field, value)
        self.db.add(instance)
        await self.db.flush()
        await self.db.refresh(instance)
        return instance

    async def soft_delete(
        self,
        instance   : ModelType,
        deleted_by : UUID,
    ) -> ModelType:
        instance.is_deleted = True
        instance.deleted_at = datetime.utcnow()
        instance.deleted_by = deleted_by
        self.db.add(instance)
        await self.db.flush()
        return instance

    async def exists_by_code(self, code: str) -> bool:
        result = await self.db.execute(
            select(func.count()).select_from(self.model).where(
                and_(
                    self.model.code       == code,
                    self.model.is_deleted == False,
                )
            )
        )
        return result.scalar_one() > 0