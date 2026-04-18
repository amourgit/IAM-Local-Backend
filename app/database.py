from sqlalchemy.ext.asyncio import (
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)
from sqlalchemy.orm import DeclarativeBase
from app.config import settings

engine = create_async_engine(
    settings.DATABASE_URL,
    echo        = settings.DEBUG,
    pool_size   = 10,
    max_overflow= 20,
)

AsyncSessionLocal = async_sessionmaker(
    bind         = engine,
    class_       = AsyncSession,
    expire_on_commit = False,
    autocommit   = False,
    autoflush    = False,
)


class Base(DeclarativeBase):
    pass


async def get_db() -> AsyncSession:
    async with AsyncSessionLocal() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise
        finally:
            await session.close()


async def get_db_session() -> AsyncSession:
    """Retourne une session de base de données pour utilisation directe."""
    return AsyncSessionLocal()
