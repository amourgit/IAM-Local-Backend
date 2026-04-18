"""
Token Manager Principal - Orchestrateur central du système d'authentification
"""

import logging
from datetime import datetime, timedelta
from typing import Dict, Optional, Tuple, Any, List
from uuid import UUID
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.infrastructure.cache.redis import CacheService
from app.core.exceptions import AuthenticationError, TokenError, ValidationError, NotFoundError

from .access_token_service import AccessTokenService
from .refresh_token_service import RefreshTokenService
from .token_blacklist_service import TokenBlacklistService
from .session_manager import SessionManager
from .token_validator import TokenValidator
from .sync_service import SyncService
from .token_config_service import get_token_config_service
from .device_analysis_service import DeviceAnalysisService

logger = logging.getLogger(__name__)


class TokenManager:

    def __init__(self):
        self.cache = CacheService()
        self.validator = TokenValidator()
        self.access_tokens = AccessTokenService()
        self.refresh_tokens = RefreshTokenService()
        self.blacklist = TokenBlacklistService(self.cache)
        self.sessions = SessionManager(self.cache)
        self.sync = SyncService()
        self.config_service = get_token_config_service()
        self.device_analyzer = DeviceAnalysisService()
        logger.info("TokenManager initialisé avec configuration dynamique et device tracking")

    # ── Authentification Locale ──────────────────────────────────────

    async def authenticate_user(
        self,
        username: str,
        password: str,
        user_agent: Optional[str] = None,
        ip_address: Optional[str] = None,
        location: Optional[str] = None
    ) -> Dict[str, Any]:
        from app.services.auth_service import AuthService
        from app.database import get_db

        async for db in get_db():
            await self.config_service.refresh_configuration_cache(db)
            auth_service = AuthService(db)

            try:
                user_data = await auth_service.authenticate_local(
                    username=username,
                    password=password
                )

                await self._check_session_limits(user_data["id"], db)

                device_info = self.device_analyzer.analyze_user_agent(user_agent or '')

                session_id = await self.sessions.create_session(
                    user_id=user_data["id"],
                    user_agent=user_agent,
                    ip_address=ip_address,
                    device_info=device_info,
                    location=location
                )

                # Durées depuis la configuration
                access_lifetime = await self.config_service.get_access_token_lifetime_minutes(db)
                refresh_lifetime_minutes = await self.config_service.get_refresh_token_lifetime_minutes(db)

                access_token = self.access_tokens.create_token(
                    user_id          = user_data["id"],
                    session_id       = session_id,
                    permissions      = user_data.get("permissions", []),      # UUIDs
                    permission_codes = user_data.get("permission_codes", []), # codes
                    roles            = user_data.get("roles", []),
                    type_profil      = user_data.get("type_profil"),
                    expires_minutes  = access_lifetime,
                    custom_claims    = {
                        "user_id_national" : user_data.get("user_id_national"),
                        "statut"           : user_data.get("statut"),
                        "groupes"          : user_data.get("groupes", []),
                    },
                )

                refresh_token = self.refresh_tokens.create_token(
                    user_id=user_data["id"],
                    session_id=session_id,
                    expires_minutes=refresh_lifetime_minutes,
                )

                await self.refresh_tokens.store_token(
                    token=refresh_token,
                    user_id=user_data["id"],
                    session_id=session_id
                )

                logger.info(f"Authentification réussie pour {username} - Device: {self.device_analyzer.get_device_summary(device_info)}")

                return {
                    "access_token": access_token,
                    "refresh_token": refresh_token,
                    "token_type": "bearer",
                    "expires_in": access_lifetime * 60,
                    "user": {
                        "id": str(user_data["id"]),
                        "username": user_data["username"],
                        "nom": user_data["nom"],
                        "prenom": user_data["prenom"],
                        "type_profil": user_data["type_profil"],
                        "permissions": user_data.get("permissions", []),
                        "roles": user_data.get("roles", []),
                        "require_password_change": user_data.get("require_password_change", False)
                    },
                    "session_id": str(session_id),
                    "device_info": device_info
                }

            except Exception as e:
                logger.warning(f"Échec authentification pour {username}: {str(e)}")
                raise AuthenticationError("Identifiants invalides")

    async def _check_session_limits(self, user_id: UUID, db: AsyncSession) -> None:
        max_sessions = await self.config_service.get_max_sessions_per_user(db)
        active_sessions = await self.sessions.get_user_sessions(user_id)
        active_count = len([s for s in active_sessions if s.get("status") == "active"])

        if active_count >= max_sessions:
            sorted_sessions = sorted(
                active_sessions,
                key=lambda s: s.get("created_at", datetime.min.isoformat())
            )
            oldest_session = sorted_sessions[0]
            await self.revoke_session(
                session_id=oldest_session["id"],
                reason="session_limit_exceeded"
            )
            logger.info(f"Limite de sessions atteinte pour user {user_id}, session la plus ancienne révoquée")

    # ── Rafraîchissement de Token ────────────────────────────────────

    async def refresh_access_token(self, refresh_token: str, db: AsyncSession) -> Dict[str, Any]:
        await self.config_service.refresh_configuration_cache(db)

        try:
            payload = await self.refresh_tokens.validate_token(refresh_token)
            user_id = UUID(payload["sub"])
            session_id = UUID(payload["session_id"])

            session = await self.sessions.get_session(session_id)
            if not session or session["user_id"] != str(user_id):
                raise TokenError("Session invalide")

            if await self.blacklist.is_blacklisted(str(session_id)):
                raise TokenError("Session révoquée")

            access_lifetime = await self.config_service.get_access_token_lifetime_minutes(db)

            new_access_token = self.access_tokens.create_token(
                user_id          = user_id,
                session_id       = session_id,
                permissions      = payload.get("permissions", []),
                permission_codes = payload.get("permission_codes", []),
                roles            = payload.get("roles", []),
                expires_minutes  = access_lifetime,
            )

            response_data = {
                "access_token": new_access_token,
                "token_type": "bearer",
                "expires_in": access_lifetime * 60
            }

            config = await self.config_service.get_config(db)
            if config.get('enable_token_rotation', True):
                refresh_lifetime_minutes = await self.config_service.get_refresh_token_lifetime_minutes(db)
                new_refresh_token = self.refresh_tokens.create_token(
                    user_id=user_id,
                    session_id=session_id,
                    expires_minutes=refresh_lifetime_minutes,
                )
                await self.refresh_tokens.update_token(
                    old_token=refresh_token,
                    new_token=new_refresh_token,
                    user_id=user_id,
                    session_id=session_id
                )
                response_data["refresh_token"] = new_refresh_token
                logger.info(f"Tokens rotatifs rafraîchis pour user {user_id}")
            else:
                logger.info(f"Token d'accès rafraîchi pour user {user_id}")

            return response_data

        except Exception as e:
            logger.warning(f"Échec rafraîchissement token: {str(e)}")
            raise TokenError("Token de rafraîchissement invalide")

    # ── Validation de Token ──────────────────────────────────────────

    async def validate_access_token(
        self,
        token: str,
        db: AsyncSession,
        request_ip: Optional[str] = None,
        request_user_agent: Optional[str] = None
    ) -> Dict[str, Any]:
        await self.config_service.refresh_configuration_cache(db)

        try:
            payload = self.access_tokens.validate_token(token)
            user_id = UUID(payload["sub"])
            session_id = UUID(payload["session_id"])

            session = await self.sessions.get_session(session_id)
            if not session:
                raise TokenError("Session expirée")

            if await self.blacklist.is_blacklisted(str(session_id)):
                raise TokenError("Session révoquée")

            config = await self.config_service.get_config(db)

            if config.get('enable_ip_validation', True) and request_ip and session.get("ip_address"):
                if session["ip_address"] != request_ip:
                    logger.warning(f"IP mismatch pour session {session_id}: {request_ip} != {session['ip_address']}")
                    if config.get('enable_blacklist', True):
                        await self.blacklist.blacklist_session(
                            session_id=str(session_id),
                            reason="ip_mismatch",
                            ttl_minutes=config.get('blacklist_ttl_minutes', 1440)
                        )
                    raise TokenError("Adresse IP non autorisée")

            await self._check_iam_central_status(user_id)

            return {
                "user_id": user_id,
                "session_id": session_id,
                "permissions": payload.get("permissions", []),
                "roles": payload.get("roles", []),
                "type_profil": payload.get("type_profil"),
                "is_admin": payload.get("is_admin", False),
                "device_info": session.get("device_info", {})
            }

        except Exception as e:
            logger.warning(f"Token invalide: {str(e)}")
            raise TokenError("Token d'accès invalide")

    # ── Révocation ───────────────────────────────────────────────────

    async def revoke_session(self, session_id: UUID, reason: str = "manual") -> None:
        try:
            await self.blacklist.blacklist_session(
                session_id=str(session_id),
                reason=reason,
                ttl_minutes=settings.SESSION_BLACKLIST_TTL_MINUTES
            )
            await self.refresh_tokens.revoke_by_session(session_id)
            await self.sessions.revoke_session(session_id)
            logger.info(f"Session {session_id} révoquée: {reason}")
        except Exception as e:
            logger.error(f"Erreur révocation session {session_id}: {str(e)}")
            raise

    async def revoke_user_sessions(self, user_id: UUID, reason: str = "user_suspended") -> int:
        try:
            sessions = await self.sessions.get_user_sessions(user_id)
            revoked_count = 0
            for session in sessions:
                if session["status"] == "active":
                    await self.revoke_session(session_id=session["id"], reason=reason)
                    revoked_count += 1
            logger.info(f"{revoked_count} sessions révoquées pour user {user_id}")
            return revoked_count
        except Exception as e:
            logger.error(f"Erreur révocation sessions user {user_id}: {str(e)}")
            raise

    # ── Synchronisation IAM Central ──────────────────────────────────

    async def sync_user_from_iam_central(self, user_id_national: str) -> Optional[Dict[str, Any]]:
        if not settings.IAM_CENTRAL_ENABLED:
            return None
        try:
            user_data = await self.sync.get_user_from_iam_central(user_id_national)
            if user_data:
                local_profile = await self._create_or_update_local_profile(user_data)
                logger.info(f"Profil synchronisé depuis IAM Central: {user_id_national}")
                return local_profile
        except Exception as e:
            logger.warning(f"Échec synchronisation IAM Central pour {user_id_national}: {str(e)}")
        return None

    async def check_user_status_iam_central(self, user_id: UUID) -> Dict[str, Any]:
        if not settings.IAM_CENTRAL_ENABLED:
            return {"status": "active", "actions": []}
        try:
            from app.database import get_db
            from app.repositories.profil_local import ProfilLocalRepository
            async for db in get_db():
                repo = ProfilLocalRepository(db)
                profile = await repo.get_by_id(user_id)
                if profile and profile.user_id_national:
                    return await self.sync.check_user_status(profile.user_id_national)
        except Exception as e:
            logger.warning(f"Erreur vérification statut IAM Central pour {user_id}: {str(e)}")
        return {"status": "unknown", "actions": []}

    # ── Utilitaires Privés ───────────────────────────────────────────

    async def _check_iam_central_status(self, user_id: UUID) -> None:
        if not settings.IAM_CENTRAL_ENABLED:
            return

        cache_key = f"iam_central_status:{user_id}"
        cached_status = await self.cache.get(cache_key)

        if cached_status:
            if cached_status["status"] != "active":
                raise TokenError(f"Compte suspendu: {cached_status.get('reason', 'Raison inconnue')}")
            return

        status = await self.check_user_status_iam_central(user_id)
        await self.cache.set(cache_key, status, ttl_seconds=300)

        if status["status"] != "active":
            raise TokenError(f"Compte suspendu: {status.get('reason', 'Raison inconnue')}")

    async def _create_or_update_local_profile(self, iam_central_data: Dict[str, Any]) -> Dict[str, Any]:
        from app.database import get_db
        from app.services.profil_service import ProfilService
        async for db in get_db():
            service = ProfilService(db)
            return await service.create_or_update_from_iam_central(iam_central_data)

    # ── Métriques ────────────────────────────────────────────────────

    async def get_metrics(self) -> Dict[str, Any]:
        return {
            "active_sessions": await self.sessions.count_active_sessions(),
            "blacklisted_sessions": await self.blacklist.count_blacklisted(),
            "tokens_issued_today": await self._count_tokens_issued_today(),
            "sync_status": await self.sync.get_sync_status(),
            "config_loaded": self.config_service.is_config_loaded(),
        }

    async def get_user_sessions_detailed(self, user_id: UUID) -> List[Dict[str, Any]]:
        sessions = await self.sessions.get_user_sessions(user_id)
        detailed_sessions = []
        for session in sessions:
            device_info = session.get("device_info", {})
            device_summary = self.device_analyzer.get_device_summary(device_info) if device_info else "Unknown Device"
            detailed_sessions.append({
                **session,
                "device_summary": device_summary,
                "device_category": self.device_analyzer.get_device_category(device_info),
                "os_category": self.device_analyzer.get_os_category(device_info),
                "browser_category": self.device_analyzer.get_browser_category(device_info)
            })
        return detailed_sessions

    async def get_configuration_status(self) -> Dict[str, Any]:
        return {
            "config_loaded": self.config_service.is_config_loaded(),
            "active_config_name": self.config_service.get_active_config_name(),
        }

    async def cleanup_expired_tokens(self) -> Dict[str, Any]:
        try:
            expired_sessions = await self.sessions.cleanup_expired_sessions()
            expired_blacklist = await self.blacklist.cleanup_expired_entries()
            expired_refresh = await self.refresh_tokens.cleanup_expired_tokens()
            result = {
                "expired_sessions_cleaned": expired_sessions,
                "expired_blacklist_cleaned": expired_blacklist,
                "expired_refresh_tokens_cleaned": expired_refresh,
                "total_cleaned": expired_sessions + expired_blacklist + expired_refresh,
                "cleanup_timestamp": datetime.utcnow().isoformat()
            }
            logger.info(f"Nettoyage terminé: {result}")
            return result
        except Exception as e:
            logger.error(f"Erreur lors du nettoyage: {e}")
            raise

    async def _count_tokens_issued_today(self) -> int:
        today = datetime.now().strftime("%Y-%m-%d")
        count = await self.cache.get(f"tokens_issued:{today}")
        return count or 0
