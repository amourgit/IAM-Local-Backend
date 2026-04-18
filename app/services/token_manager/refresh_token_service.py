"""
Service de gestion des refresh tokens.
"""
import time
import hashlib
import secrets
import logging
from datetime import datetime, timedelta
from typing import Dict, Any, Optional
from uuid import UUID
from datetime import timezone

import jwt

from app.config import settings
from app.infrastructure.cache.redis import CacheService
from app.core.exceptions import TokenError

logger = logging.getLogger(__name__)


class RefreshTokenService:

    def __init__(self, cache: Optional[CacheService] = None):
        self.cache = cache or CacheService()
        self.secret_key = settings.JWT_SECRET_KEY
        self.algorithm = settings.JWT_ALGORITHM
        self.expire_days = settings.REFRESH_TOKEN_EXPIRE_DAYS

    def create_token(
        self,
        user_id: UUID,
        session_id: UUID,
        expires_minutes: int = None,          # ✅ Paramètre ajouté
    ) -> str:
        now = datetime.utcfromtimestamp(time.time())

        if expires_minutes is not None:
            expire = now + timedelta(minutes=expires_minutes)
        else:
            expire = now + timedelta(days=self.expire_days)

        token_id = secrets.token_urlsafe(32)

        payload = {
            "iss": "iam-local",
            "sub": str(user_id),
            "iat": int(now.timestamp()),
            "exp": int(expire.timestamp()),
            "session_id": str(session_id),
            "token_type": "refresh",
            "token_id": token_id,
            "version": "1.0"
        }

        try:
            token = jwt.encode(payload, self.secret_key, algorithm=self.algorithm)
            logger.debug(f"Refresh token créé pour user {user_id}, session {session_id}")
            return token
        except Exception as e:
            logger.error(f"Erreur création refresh token: {str(e)}")
            raise TokenError("Erreur lors de la création du refresh token")

    async def store_token(
        self,
        token: str,
        user_id: UUID,
        session_id: UUID,
        metadata: Dict[str, Any] = None
    ) -> None:
        try:
            payload = jwt.decode(token, options={"verify_signature": False})
            token_id = payload.get("token_id")

            if not token_id:
                raise TokenError("Token ID manquant dans le refresh token")

            token_hash = hashlib.sha256(token.encode()).hexdigest()
            cache_key = f"refresh_token:{token_id}"

            token_data = {
                "hash": token_hash,
                "user_id": str(user_id),
                "session_id": str(session_id),
                "created_at": datetime.utcfromtimestamp(time.time()).isoformat(),
                "metadata": metadata or {}
            }

            ttl_seconds = self.expire_days * 24 * 60 * 60
            await self.cache.set(cache_key, token_data, ttl_seconds=ttl_seconds)
            logger.debug(f"Refresh token stocké: {token_id}")

        except Exception as e:
            logger.error(f"Erreur stockage refresh token: {str(e)}")
            raise TokenError("Erreur lors du stockage du refresh token")

    async def validate_token(self, token: str) -> Dict[str, Any]:
        try:
            payload = jwt.decode(
                token,
                self.secret_key,
                algorithms=[self.algorithm],
                options={
                    "verify_signature": True,
                    "verify_exp": True,
                    "verify_iat": True,
                    "verify_iss": True,
                    "require": ["iss", "sub", "exp", "token_id", "session_id"]
                }
            )

            if payload.get("iss") != "iam-local":
                raise TokenError("Issuer invalide pour refresh token")

            if payload.get("token_type") != "refresh":
                raise TokenError("Type de token invalide")

            token_id = payload.get("token_id")
            cache_key = f"refresh_token:{token_id}"
            stored_data = await self.cache.get(cache_key)

            if not stored_data:
                raise TokenError("Refresh token révoqué ou expiré")

            token_hash = hashlib.sha256(token.encode()).hexdigest()
            if stored_data["hash"] != token_hash:
                raise TokenError("Refresh token compromis")

            logger.debug(f"Refresh token validé: {token_id}")
            return payload

        except jwt.ExpiredSignatureError:
            raise TokenError("Refresh token expiré")
        except jwt.InvalidSignatureError:
            raise TokenError("Signature du refresh token invalide")
        except jwt.InvalidTokenError as e:
            raise TokenError(f"Refresh token invalide: {str(e)}")
        except Exception as e:
            logger.error(f"Erreur validation refresh token: {str(e)}")
            raise TokenError("Erreur lors de la validation du refresh token")

    async def revoke_token(self, token: str) -> None:
        try:
            payload = jwt.decode(token, options={"verify_signature": False})
            token_id = payload.get("token_id")
            if token_id:
                await self.cache.delete(f"refresh_token:{token_id}")
                logger.info(f"Refresh token révoqué: {token_id}")
        except Exception as e:
            logger.warning(f"Erreur révocation refresh token: {str(e)}")

    async def revoke_by_session(self, session_id: UUID) -> None:
        try:
            all_keys = await self.cache.keys("refresh_token:*")
            revoked_count = 0
            for key in all_keys:
                token_data = await self.cache.get(key)
                if token_data and token_data.get("session_id") == str(session_id):
                    await self.cache.delete(key)
                    revoked_count += 1
            logger.info(f"{revoked_count} refresh tokens révoqués pour session {session_id}")
        except Exception as e:
            logger.error(f"Erreur révocation refresh tokens session {session_id}: {str(e)}")

    async def revoke_by_user(self, user_id: UUID) -> int:
        try:
            all_keys = await self.cache.keys("refresh_token:*")
            revoked_count = 0
            for key in all_keys:
                token_data = await self.cache.get(key)
                if token_data and token_data.get("user_id") == str(user_id):
                    await self.cache.delete(key)
                    revoked_count += 1
            logger.info(f"{revoked_count} refresh tokens révoqués pour user {user_id}")
            return revoked_count
        except Exception as e:
            logger.error(f"Erreur révocation refresh tokens user {user_id}: {str(e)}")
            raise

    async def update_token(self, old_token: str, new_token: str, user_id: UUID, session_id: UUID) -> None:
        await self.revoke_token(old_token)
        await self.store_token(token=new_token, user_id=user_id, session_id=session_id)

    async def get_user_tokens(self, user_id: UUID) -> list:
        try:
            all_keys = await self.cache.keys("refresh_token:*")
            user_tokens = []
            for key in all_keys:
                token_data = await self.cache.get(key)
                if token_data and token_data.get("user_id") == str(user_id):
                    user_tokens.append({
                        "token_id": key.split(":")[1],
                        "session_id": token_data.get("session_id"),
                        "created_at": token_data.get("created_at"),
                        "metadata": token_data.get("metadata", {})
                    })
            return user_tokens
        except Exception as e:
            logger.error(f"Erreur récupération tokens user {user_id}: {str(e)}")
            return []

    def decode_token_without_validation(self, token: str) -> Optional[Dict[str, Any]]:
        try:
            return jwt.decode(token, options={"verify_signature": False})
        except Exception:
            return None

    def _is_token_expired(self, payload: Dict[str, Any]) -> bool:
        exp = payload.get("exp")
        return exp is None or exp < time.time()

    async def count_active_tokens(self) -> int:
        try:
            keys = await self.cache.keys("refresh_token:*")
            return len(keys)
        except Exception:
            return 0

    async def cleanup_expired_tokens(self) -> int:
        return 0
