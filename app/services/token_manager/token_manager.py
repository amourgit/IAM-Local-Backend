"""
Token Manager v2 — Orchestrateur central complet du système d'authentification.

Fonctionnalités :
- Auth locale et SSO IAM Central
- 1 session active par device (fingerprint)
- Rotation automatique des refresh tokens
- Détection d'anomalies (IP change, device change, replay, rate limit)
- Device registry par profil
- Audit trail complet
- Révocation en cascade
- Nettoyage automatique
"""
import logging
from datetime import datetime, timezone
from typing import Dict, Optional, Any, List
from uuid import UUID

from app.config import settings
from app.infrastructure.cache.redis import CacheService
from app.core.exceptions import AuthenticationError, TokenError

from .access_token_service import AccessTokenService
from .refresh_token_service import RefreshTokenService
from .token_blacklist_service import TokenBlacklistService
from .session_manager import SessionManager
from .token_validator import TokenValidator
from .sync_service import SyncService
from .token_config_service import get_token_config_service
from .device_analysis_service import DeviceAnalysisService
from .device_registry import DeviceRegistry, fingerprint
from .anomaly_detector import AnomalyDetector
from .token_audit import TokenAuditService

logger = logging.getLogger(__name__)


class TokenManager:
    """
    Orchestrateur central — point d'entrée unique pour toutes les opérations
    liées aux tokens, sessions et devices.
    """

    def __init__(self):
        self.cache          = CacheService()
        self.validator      = TokenValidator()
        self.access_svc     = AccessTokenService()
        self.refresh_svc    = RefreshTokenService()
        self.blacklist      = TokenBlacklistService(self.cache)
        self.sessions       = SessionManager(self.cache)
        self.devices        = DeviceRegistry(self.cache)
        self.anomalies      = AnomalyDetector(self.cache)
        self.audit          = TokenAuditService(self.cache)
        self.sync           = SyncService()
        self.config_svc     = get_token_config_service()
        self.device_analyzer= DeviceAnalysisService()

    # ══════════════════════════════════════════════════════════════
    # AUTHENTIFICATION
    # ══════════════════════════════════════════════════════════════

    async def authenticate_user(
        self,
        username   : str,
        password   : str,
        user_agent : Optional[str] = None,
        ip_address : Optional[str] = None,
        location   : Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Authentification locale credentials → tokens.
        Gère : device fingerprint, session unique par device, audit.
        """
        from app.services.auth_service import AuthService
        from app.database import get_db

        async for db in get_db():
            await self.config_svc.refresh_configuration_cache(db)
            auth_service = AuthService(db)

            try:
                user_data = await auth_service.authenticate_local(
                    username=username, password=password
                )
            except Exception as e:
                logger.warning(f"Échec auth {username}: {e}")
                raise AuthenticationError("Identifiants invalides")

            profil_id   = user_data["id"]
            device_info = self.device_analyzer.analyze_user_agent(user_agent or "")
            device_id   = device_info.get("device_id") or fingerprint(user_agent or "", ip_address or "")

            # Si le device avait une session active → la révoquer (1 par device)
            existing_session = await self.devices.get_active_session(device_id)
            if existing_session:
                await self._revoke_session_internal(
                    session_id=UUID(existing_session),
                    profil_id=profil_id,
                    reason="new_login_same_device",
                )

            # Enregistrer le device
            await self.devices.register(
                profil_id=profil_id, device_id=device_id,
                device_info=device_info, ip_address=ip_address or "",
                user_agent=user_agent or "",
            )

            # Créer la session
            access_ttl  = await self.config_svc.get_access_token_lifetime_minutes(db)
            refresh_ttl = await self.config_svc.get_refresh_token_lifetime_minutes(db)

            session_id = await self.sessions.create_session(
                user_id    = profil_id,
                user_agent = user_agent,
                ip_address = ip_address,
                device_info= device_info,
                location   = location,
            )

            # Lier session → device
            await self.devices.set_active_session(device_id, str(session_id))

            # Créer les tokens
            access_token = self.access_svc.create_token(
                user_id          = profil_id,
                session_id       = session_id,
                permissions      = user_data.get("permissions", []),
                permission_codes = user_data.get("permission_codes", []),
                roles            = user_data.get("roles", []),
                type_profil      = user_data.get("type_profil"),
                expires_minutes  = access_ttl,
                custom_claims    = {
                    "user_id_national" : user_data.get("user_id_national"),
                    "statut"           : user_data.get("statut"),
                    "groupes"          : user_data.get("groupes", []),
                    "compte_id"        : user_data.get("compte_id"),
                    "device_id"        : device_id,
                    "is_bootstrap"     : user_data.get("is_bootstrap", False),
                },
            )

            refresh_token = self.refresh_svc.create_token(
                user_id=profil_id, session_id=session_id,
                expires_minutes=refresh_ttl,
            )
            await self.refresh_svc.store_token(
                token=refresh_token, user_id=profil_id, session_id=session_id
            )

            # Audit
            await self.audit.log(
                event_type = "login_success",
                profil_id  = profil_id,
                session_id = str(session_id),
                device_id  = device_id,
                ip_address = ip_address,
                details    = {"username": username, "device_type": device_info.get("device_type")},
            )

            return {
                "access_token" : access_token,
                "refresh_token": refresh_token,
                "token_type"   : "bearer",
                "expires_in"   : access_ttl * 60,
                "session_id"   : str(session_id),
                "device_id"    : device_id,
                "device_info"  : device_info,
                "user"         : {
                    "id"                     : str(profil_id),
                    "username"               : user_data.get("username"),
                    "nom"                    : user_data.get("nom"),
                    "prenom"                 : user_data.get("prenom"),
                    "email"                  : user_data.get("email"),
                    "type_profil"            : user_data.get("type_profil"),
                    "permissions"            : user_data.get("permissions", []),
                    "permission_codes"       : user_data.get("permission_codes", []),
                    "roles"                  : user_data.get("roles", []),
                    "require_password_change": user_data.get("require_password_change", False),
                    "compte_id"              : user_data.get("compte_id"),
                },
            }

    # ══════════════════════════════════════════════════════════════
    # REFRESH TOKEN
    # ══════════════════════════════════════════════════════════════

    async def refresh_access_token(
        self,
        refresh_token: str,
        db,
        ip_address   : Optional[str] = None,
        user_agent   : Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Rafraîchit l'access token.
        Vérifie : session active, blacklist, rate limit, device.
        Rotation automatique du refresh token.
        """
        await self.config_svc.refresh_configuration_cache(db)

        try:
            payload    = await self.refresh_svc.validate_token(refresh_token)
            profil_id  = UUID(payload["sub"])
            session_id = UUID(payload["session_id"])

            # Vérifier rate limit
            if await self.anomalies.check_refresh_rate(profil_id):
                await self.audit.log("rate_limit_exceeded", profil_id,
                                     str(session_id), ip_address=ip_address,
                                     severity="warning")
                raise TokenError("Trop de demandes de refresh")

            # Vérifier la session
            session = await self.sessions.get_session_raw(session_id)
            if not session or session.get("status") != "active":
                raise TokenError("Session expirée ou révoquée")

            # Vérifier la blacklist
            if await self.blacklist.is_blacklisted(str(session_id)):
                raise TokenError("Session blacklistée")

            # Enregistrer le refresh
            await self.sessions.increment_refresh_count(session_id)
            await self.anomalies.record_location(profil_id, ip_address or "", str(session_id))

            access_ttl = await self.config_svc.get_access_token_lifetime_minutes(db)

            new_access = self.access_svc.create_token(
                user_id          = profil_id,
                session_id       = session_id,
                permissions      = payload.get("permissions", []),
                permission_codes = payload.get("permission_codes", []),
                roles            = payload.get("roles", []),
                type_profil      = payload.get("type_profil"),
                expires_minutes  = access_ttl,
                custom_claims    = {
                    k: v for k, v in payload.items()
                    if k not in ("iss","sub","iat","exp","jti","session_id",
                                 "token_type","version","permissions",
                                 "permission_codes","roles","type_profil")
                },
            )

            response = {"access_token": new_access, "token_type": "bearer",
                        "expires_in": access_ttl * 60}

            # Rotation refresh token
            config = await self.config_svc.get_config(db)
            if config.get("enable_token_rotation", True):
                refresh_ttl = await self.config_svc.get_refresh_token_lifetime_minutes(db)
                new_refresh = self.refresh_svc.create_token(
                    user_id=profil_id, session_id=session_id,
                    expires_minutes=refresh_ttl,
                )
                await self.refresh_svc.update_token(
                    old_token=refresh_token, new_token=new_refresh,
                    user_id=profil_id, session_id=session_id,
                )
                response["refresh_token"] = new_refresh

            await self.audit.log("token_refreshed", profil_id, str(session_id),
                                  ip_address=ip_address)
            return response

        except TokenError:
            raise
        except Exception as e:
            logger.warning(f"Refresh échoué: {e}")
            raise TokenError("Refresh token invalide")

    # ══════════════════════════════════════════════════════════════
    # VALIDATION
    # ══════════════════════════════════════════════════════════════

    async def validate_access_token(
        self,
        token      : str,
        db,
        request_ip : Optional[str] = None,
        user_agent : Optional[str] = None,
    ) -> Dict[str, Any]:
        """Valide un access token avec toutes les vérifications de sécurité."""
        await self.config_svc.refresh_configuration_cache(db)

        try:
            payload    = self.access_svc.validate_token(token)
            profil_id  = UUID(payload["sub"])
            session_id = UUID(payload["session_id"])
            device_id  = payload.get("device_id", "")

            # Session active ?
            session = await self.sessions.get_session(session_id)
            if not session or session.get("status") != "active":
                raise TokenError("Session expirée")

            # Blacklist ?
            if await self.blacklist.is_blacklisted(str(session_id)):
                raise TokenError("Session révoquée")

            # Détection changement device
            if device_id and user_agent:
                current_device = (self.device_analyzer.analyze_user_agent(user_agent)
                                  .get("device_id", ""))
                anomaly = self.anomalies.check_device_change(
                    device_id, current_device, str(session_id)
                )
                if anomaly:
                    await self.audit.log("device_change_detected", profil_id,
                                         str(session_id), device_id=device_id,
                                         ip_address=request_ip, severity="warning",
                                         details=anomaly)

            # Détection changement IP
            if request_ip:
                await self.anomalies.record_location(profil_id, request_ip, str(session_id))

            return {
                "user_id"        : profil_id,
                "session_id"     : session_id,
                "permissions"    : payload.get("permissions", []),
                "permission_codes": payload.get("permission_codes", []),
                "roles"          : payload.get("roles", []),
                "type_profil"    : payload.get("type_profil"),
                "is_admin"       : payload.get("is_admin", False),
                "device_id"      : device_id,
                "device_info"    : session.get("device_info", {}),
                "compte_id"      : payload.get("compte_id"),
            }

        except TokenError:
            raise
        except Exception as e:
            logger.warning(f"Token invalide: {e}")
            raise TokenError("Token d'accès invalide")

    # ══════════════════════════════════════════════════════════════
    # RÉVOCATION
    # ══════════════════════════════════════════════════════════════

    async def revoke_session(self, session_id: UUID, reason: str = "manual") -> None:
        """Révoque une session et invalide les tokens associés."""
        session = await self.sessions.get_session_raw(session_id)
        if session:
            profil_id = UUID(session.get("user_id", str(session_id)))
            device_id = session.get("device_id", "")
            await self._revoke_session_internal(session_id, profil_id, reason, device_id)

    async def _revoke_session_internal(
        self,
        session_id: UUID,
        profil_id : UUID,
        reason    : str,
        device_id : str = "",
    ) -> None:
        await self.blacklist.blacklist_session(
            session_id=str(session_id), reason=reason,
            ttl_minutes=settings.SESSION_BLACKLIST_TTL_MINUTES
        )
        await self.refresh_svc.revoke_by_session(session_id)
        await self.sessions.revoke_session(session_id, reason)
        if device_id:
            await self.devices.clear_active_session(device_id)
        await self.audit.log("session_revoked", profil_id, str(session_id),
                              device_id=device_id,
                              details={"reason": reason})

    async def revoke_user_sessions(self, user_id: UUID, reason: str = "manual") -> int:
        """Révoque toutes les sessions d'un profil."""
        sessions = await self.sessions.get_active_sessions(user_id)
        count    = 0
        for s in sessions:
            await self.revoke_session(UUID(s["id"]), reason)
            count += 1
        await self.devices.revoke_all_devices(user_id)
        await self.audit.log("all_sessions_revoked", user_id,
                              details={"count": count, "reason": reason},
                              severity="warning")
        return count

    async def revoke_device(self, profil_id: UUID, device_id: str) -> None:
        """Révoque un device spécifique et sa session active."""
        session_id_str = await self.devices.get_active_session(device_id)
        if session_id_str:
            await self._revoke_session_internal(
                session_id=UUID(session_id_str), profil_id=profil_id,
                reason="device_revoked", device_id=device_id,
            )
        await self.devices.revoke_device(device_id, profil_id)

    # ══════════════════════════════════════════════════════════════
    # DEVICES
    # ══════════════════════════════════════════════════════════════

    async def get_user_devices(self, profil_id: UUID) -> List[Dict[str, Any]]:
        """Retourne tous les devices connus d'un profil."""
        return await self.devices.get_profil_devices(profil_id)

    async def trust_device(self, device_id: str) -> bool:
        """Marque un device comme de confiance."""
        return await self.devices.trust_device(device_id)

    # ══════════════════════════════════════════════════════════════
    # SESSIONS
    # ══════════════════════════════════════════════════════════════

    async def get_user_sessions_detailed(self, user_id: UUID) -> List[Dict[str, Any]]:
        """Retourne les sessions avec détails device."""
        sessions = await self.sessions.get_user_sessions(user_id)
        result   = []
        for s in sessions:
            device_info = s.get("device_info", {})
            result.append({
                **s,
                "device_summary" : self.device_analyzer.get_device_summary(device_info),
                "device_category": self.device_analyzer.get_device_category(device_info),
                "os_category"    : self.device_analyzer.get_os_category(device_info),
                "browser_category": self.device_analyzer.get_browser_category(device_info),
            })
        return result

    async def get_sessions_stats(self, user_id: UUID) -> Dict[str, Any]:
        """Statistiques des sessions d'un profil."""
        return await self.sessions.get_sessions_stats(user_id)

    # ══════════════════════════════════════════════════════════════
    # AUDIT
    # ══════════════════════════════════════════════════════════════

    async def get_token_audit(
        self,
        profil_id : UUID,
        limit     : int  = 50,
    ) -> List[Dict[str, Any]]:
        """Historique d'audit des tokens d'un profil."""
        return await self.audit.get_history(profil_id, limit=limit)

    # ══════════════════════════════════════════════════════════════
    # SYNCHRONISATION IAM CENTRAL
    # ══════════════════════════════════════════════════════════════

    async def sync_user_from_iam_central(
        self, user_id_national: str
    ) -> Optional[Dict[str, Any]]:
        if not settings.IAM_CENTRAL_ENABLED:
            return None
        try:
            return await self.sync.get_user_from_iam_central(user_id_national)
        except Exception as e:
            logger.warning(f"Sync IAM Central échoué {user_id_national}: {e}")
            return None

    async def check_user_status_iam_central(self, user_id: UUID) -> Dict[str, Any]:
        if not settings.IAM_CENTRAL_ENABLED:
            return {"status": "active", "actions": []}
        try:
            from app.database import get_db
            from app.repositories.compte_local import CompteLocalRepository
            from app.repositories.profil_local import ProfilLocalRepository
            async for db in get_db():
                profil_repo = ProfilLocalRepository(db)
                profil = await profil_repo.get_with_compte(user_id)
                if profil and profil.compte and profil.compte.user_id_national:
                    return await self.sync.check_user_status(
                        str(profil.compte.user_id_national)
                    )
                break
        except Exception as e:
            logger.warning(f"Statut IAM Central {user_id}: {e}")
        return {"status": "unknown", "actions": []}

    # ══════════════════════════════════════════════════════════════
    # MÉTRIQUES ET MAINTENANCE
    # ══════════════════════════════════════════════════════════════

    async def get_metrics(self) -> Dict[str, Any]:
        """Métriques globales du système de tokens."""
        active = await self.sessions.count_active_sessions()
        black  = await self.blacklist.count_blacklisted()
        today  = datetime.now(timezone.utc).strftime("%Y-%m-%d")
        issued = await self.cache.get(f"iam:tokens:issued:{today}") or 0
        return {
            "active_sessions"      : active,
            "blacklisted_sessions" : black,
            "tokens_issued_today"  : issued,
            "sync_status"          : await self.sync.get_sync_status(),
            "config_loaded"        : self.config_svc.is_config_loaded(),
        }

    async def get_configuration_status(self) -> Dict[str, Any]:
        return {
            "config_loaded"      : self.config_svc.is_config_loaded(),
            "active_config_name" : self.config_svc.get_active_config_name(),
        }

    async def cleanup_expired_tokens(self) -> Dict[str, Any]:
        expired_sessions  = await self.sessions.cleanup_expired_sessions()
        expired_blacklist = await self.blacklist.cleanup_expired_entries()
        expired_refresh   = await self.refresh_svc.cleanup_expired_tokens()
        result = {
            "expired_sessions_cleaned" : expired_sessions,
            "expired_blacklist_cleaned": expired_blacklist,
            "expired_refresh_cleaned"  : expired_refresh,
            "total_cleaned"            : expired_sessions + expired_blacklist + expired_refresh,
            "timestamp"                : datetime.now(timezone.utc).isoformat(),
        }
        logger.info(f"Cleanup: {result}")
        return result

    # Rétro-compatibilité
    async def _check_session_limits(self, user_id: UUID, db) -> None:
        pass  # Géré dans create_session via _enforce_session_limit
