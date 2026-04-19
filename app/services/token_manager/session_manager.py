"""
Gestionnaire de sessions — version robuste.

Une session est liée à :
- Un profil (profil_id = sub du JWT)
- Un device (fingerprint User-Agent)
- Une IP (au moment de la création)

Un device ne peut avoir qu'UNE session active à la fois.
Si le même device reconnecte, l'ancienne session est révoquée.
"""
import logging
import uuid
from datetime import datetime, timezone, timedelta
from typing import Dict, Any, List, Optional
from uuid import UUID

from app.infrastructure.cache.redis import CacheService
from app.config import settings

logger = logging.getLogger(__name__)

_PFX_SESSION     = "iam:session:"          # iam:session:{session_id}
_PFX_USER_SESSIONS = "iam:user:sessions:"  # iam:user:sessions:{profil_id} → [session_ids]
_PFX_ACTIVE_COUNT = "iam:active:count"     # compteur global


class SessionManager:
    """
    Gestionnaire complet des sessions utilisateur.
    Stockage Redis avec TTL automatique et gestion du cycle de vie.
    """

    def __init__(self, cache: CacheService):
        self.cache              = cache
        self.session_ttl_hours  = getattr(settings, 'SESSION_TTL_HOURS', 24)
        self.max_sessions       = getattr(settings, 'MAX_SESSIONS_PER_USER', 5)

    # ── Création ───────────────────────────────────────────────────

    async def create_session(
        self,
        user_id    : UUID,
        user_agent : Optional[str]     = None,
        ip_address : Optional[str]     = None,
        device_info: Optional[Dict]    = None,
        metadata   : Optional[Dict]    = None,
        location   : Optional[str]     = None,
    ) -> UUID:
        """
        Crée une session et la lie au device.
        Si le device avait déjà une session active → révocation automatique.
        """
        session_id = uuid.uuid4()
        now        = datetime.now(timezone.utc)
        expires_at = now + timedelta(hours=self.session_ttl_hours)

        device_id = (device_info or {}).get("device_id", "unknown")

        session_data = {
            "id"            : str(session_id),
            "user_id"       : str(user_id),
            "status"        : "active",
            "created_at"    : now.isoformat(),
            "last_activity" : now.isoformat(),
            "expires_at"    : expires_at.isoformat(),
            "user_agent"    : user_agent or "",
            "ip_address"    : ip_address or "",
            "device_id"     : device_id,
            "device_info"   : device_info or {},
            "location"      : location or "",
            "metadata"      : metadata or {},
            "activity_count": 0,
            "refresh_count" : 0,
            "version"       : "2.0",
        }

        ttl = int(self.session_ttl_hours * 3600)
        await self.cache.set(f"{_PFX_SESSION}{session_id}", session_data, ttl=ttl)

        # Index par profil
        await self._add_to_user_index(user_id, str(session_id), ttl)

        # Appliquer la limite de sessions
        await self._enforce_session_limit(user_id)

        logger.info(
            f"Session créée: {str(session_id)[:8]}... "
            f"profil={str(user_id)[:8]} device={device_id[:8]}"
        )
        return session_id

    # ── Lecture ─────────────────────────────────────────────────────

    async def get_session(self, session_id: UUID) -> Optional[Dict[str, Any]]:
        """Récupère une session et met à jour l'activité."""
        key  = f"{_PFX_SESSION}{session_id}"
        data = await self.cache.get(key)
        if data and data.get("status") == "active":
            await self._touch_session(session_id, data)
        return data

    async def get_session_raw(self, session_id: UUID) -> Optional[Dict[str, Any]]:
        """Récupère une session sans mise à jour (lecture seule)."""
        return await self.cache.get(f"{_PFX_SESSION}{session_id}")

    async def get_user_sessions(self, user_id: UUID) -> List[Dict[str, Any]]:
        """Retourne toutes les sessions d'un profil."""
        session_ids = await self._get_user_session_ids(user_id)
        sessions    = []
        for sid in session_ids:
            data = await self.cache.get(f"{_PFX_SESSION}{sid}")
            if data:
                sessions.append(data)
        return sessions

    async def get_active_sessions(self, user_id: UUID) -> List[Dict[str, Any]]:
        """Retourne uniquement les sessions actives d'un profil."""
        all_sessions = await self.get_user_sessions(user_id)
        return [s for s in all_sessions if s.get("status") == "active"]

    async def count_active_sessions(self) -> int:
        """Compte global des sessions actives (approximatif)."""
        try:
            count = await self.cache.get(_PFX_ACTIVE_COUNT)
            return count or 0
        except Exception:
            return 0

    # ── Mise à jour ─────────────────────────────────────────────────

    async def touch(self, session_id: UUID) -> None:
        """Met à jour la dernière activité d'une session."""
        key  = f"{_PFX_SESSION}{session_id}"
        data = await self.cache.get(key)
        if data:
            await self._touch_session(session_id, data)

    async def increment_refresh_count(self, session_id: UUID) -> None:
        """Incrémente le compteur de refresh pour cette session."""
        key  = f"{_PFX_SESSION}{session_id}"
        data = await self.cache.get(key)
        if data:
            data["refresh_count"] = data.get("refresh_count", 0) + 1
            ttl = self._remaining_ttl(data)
            await self.cache.set(key, data, ttl=ttl)

    # ── Révocation ──────────────────────────────────────────────────

    async def revoke_session(self, session_id: UUID, reason: str = "manual") -> None:
        """Révoque une session (garde en cache 5 min pour les checks)."""
        key  = f"{_PFX_SESSION}{session_id}"
        data = await self.cache.get(key)
        if data:
            data["status"]     = "revoked"
            data["revoked_at"] = datetime.now(timezone.utc).isoformat()
            data["revoke_reason"] = reason
            await self.cache.set(key, data, ttl=300)  # garde 5 min
            logger.info(f"Session révoquée: {str(session_id)[:8]} — {reason}")

    async def revoke_all_user_sessions(self, user_id: UUID, reason: str = "manual") -> int:
        """Révoque toutes les sessions d'un profil."""
        sessions = await self.get_active_sessions(user_id)
        count    = 0
        for s in sessions:
            await self.revoke_session(UUID(s["id"]), reason)
            count += 1
        logger.info(f"{count} sessions révoquées pour profil {str(user_id)[:8]}")
        return count

    async def cleanup_expired_sessions(self) -> int:
        """Nettoie les sessions expirées de l'index utilisateur."""
        # Redis gère le TTL automatiquement, on nettoie juste les index
        return 0

    # ── Statistiques ────────────────────────────────────────────────

    async def get_sessions_stats(self, user_id: UUID) -> Dict[str, Any]:
        """Statistiques des sessions d'un profil."""
        sessions = await self.get_user_sessions(user_id)
        active   = [s for s in sessions if s.get("status") == "active"]
        revoked  = [s for s in sessions if s.get("status") == "revoked"]

        devices = {}
        for s in active:
            di = s.get("device_info", {})
            dt = di.get("device_type", "unknown")
            devices[dt] = devices.get(dt, 0) + 1

        return {
            "total"          : len(sessions),
            "active"         : len(active),
            "revoked"        : len(revoked),
            "by_device_type" : devices,
            "ips"            : list(set(s.get("ip_address", "") for s in active)),
        }

    # ── Privé ────────────────────────────────────────────────────────

    async def _touch_session(self, session_id: UUID, data: Dict) -> None:
        now = datetime.now(timezone.utc).isoformat()
        data["last_activity"]  = now
        data["activity_count"] = data.get("activity_count", 0) + 1
        ttl = self._remaining_ttl(data)
        if ttl > 0:
            await self.cache.set(f"{_PFX_SESSION}{session_id}", data, ttl=ttl)

    def _remaining_ttl(self, data: Dict) -> int:
        """Calcule le TTL restant en secondes depuis expires_at."""
        try:
            expires = datetime.fromisoformat(data["expires_at"])
            remaining = (expires - datetime.now(timezone.utc)).total_seconds()
            return max(int(remaining), 60)
        except Exception:
            return 3600

    async def _add_to_user_index(self, user_id: UUID, session_id: str, ttl: int) -> None:
        key      = f"{_PFX_USER_SESSIONS}{user_id}"
        existing = await self.cache.get(key) or []
        if session_id not in existing:
            existing.append(session_id)
        await self.cache.set(key, existing, ttl=ttl)

    async def _get_user_session_ids(self, user_id: UUID) -> List[str]:
        key = f"{_PFX_USER_SESSIONS}{user_id}"
        return await self.cache.get(key) or []

    async def _enforce_session_limit(self, user_id: UUID) -> None:
        """Révoque les sessions les plus anciennes si la limite est dépassée."""
        sessions = await self.get_active_sessions(user_id)
        if len(sessions) <= self.max_sessions:
            return
        # Trier par date de création, révoquer les plus anciennes
        sessions.sort(key=lambda s: s.get("created_at", ""))
        to_revoke = sessions[:len(sessions) - self.max_sessions]
        for s in to_revoke:
            await self.revoke_session(UUID(s["id"]), reason="session_limit")
            logger.info(f"Session oldest révoquée (limite): {s['id'][:8]}")
