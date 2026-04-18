import json
import logging
from typing import Any
import redis.asyncio as aioredis
from app.config import settings

logger = logging.getLogger(__name__)

_redis_client: aioredis.Redis | None = None


async def get_redis() -> aioredis.Redis:
    global _redis_client
    if _redis_client is None:
        _redis_client = aioredis.from_url(
            settings.REDIS_URL,
            encoding         = "utf-8",
            decode_responses = True,
        )
    return _redis_client


class CacheService:
    """
    Cache Redis pour IAM Local.
    Clés principales :
    - iam:habilitations:{profil_id}  TTL 15 min
    - iam:profil:{user_id_national}  TTL 5 min
    - iam:permissions:all            TTL 1 heure
    """

    TTL_HABILITATIONS = 900    # 15 minutes
    TTL_PROFIL        = 300    # 5 minutes
    TTL_PERMISSIONS   = 3600   # 1 heure

    async def get(self, key: str) -> Any | None:
        try:
            redis  = await get_redis()
            cached = await redis.get(key)
            if cached:
                return json.loads(cached)
            return None
        except Exception as e:
            logger.warning(f"Cache GET failed — key={key} error={e}")
            return None

    async def set(
        self,
        key        : str,
        value      : Any,
        ttl        : int = TTL_HABILITATIONS,
        ttl_seconds: int = None,
    ) -> None:
        actual_ttl = ttl_seconds if ttl_seconds is not None else ttl
        try:
            redis = await get_redis()
            await redis.setex(
                key, actual_ttl, json.dumps(value, default=str)
            )
        except Exception as e:
            logger.warning(f"Cache SET failed — key={key} error={e}")

    async def delete(self, key: str) -> None:
        try:
            redis = await get_redis()
            await redis.delete(key)
        except Exception as e:
            logger.warning(f"Cache DELETE failed — key={key} error={e}")

    async def delete_pattern(self, pattern: str) -> None:
        try:
            redis = await get_redis()
            keys  = await redis.keys(pattern)
            if keys:
                await redis.delete(*keys)
        except Exception as e:
            logger.warning(
                f"Cache DELETE_PATTERN failed — "
                f"pattern={pattern} error={e}"
            )

    async def exists(self, key: str) -> bool:
        """Vérifie si une clé existe."""
        try:
            redis = await get_redis()
            return await redis.exists(key) > 0
        except Exception as e:
            logger.warning(f"Cache EXISTS failed — key={key} error={e}")
            return False

    async def keys(self, pattern: str) -> list:
        """Récupère toutes les clés correspondant au pattern."""
        try:
            redis = await get_redis()
            return await redis.keys(pattern)
        except Exception as e:
            logger.warning(f"Cache KEYS failed — pattern={pattern} error={e}")
            return []

    async def invalider_habilitations_profil(
        self, profil_id: str
    ) -> None:
        """
        Appelé après toute modification d'habilitation.
        Force le recalcul au prochain accès.
        """
        await self.delete(f"iam:habilitations:{profil_id}")

    async def invalider_toutes_habilitations(self) -> None:
        """
        Appelé après modification d'un rôle ou d'une permission.
        Invalide tous les caches d'habilitations.
        """
        await self.delete_pattern("iam:habilitations:*")

    async def invalider_permissions(self) -> None:
        await self.delete("iam:permissions:all")
