"""
Audit trail complet des événements liés aux tokens et sessions.

Chaque événement est :
- Stocké en Redis (ring buffer par profil, 100 entrées)
- Publié sur le JournalAcces (DB immuable) pour les événements critiques
"""
import logging
from datetime import datetime, timezone
from typing import Dict, Any, List, Optional
from uuid import UUID

from app.infrastructure.cache.redis import CacheService

logger = logging.getLogger(__name__)

_PFX_AUDIT = "iam:audit:token:"  # iam:audit:token:{profil_id} → list

# Événements critiques → persistés en DB
CRITICAL_EVENTS = {
    "token_revoked",
    "session_hijack_detected",
    "device_change_detected",
    "replay_attack",
    "rate_limit_exceeded",
    "impossible_travel",
    "user_locked",
    "all_sessions_revoked",
}


class TokenAuditService:
    """
    Service d'audit des événements token/session.
    Ring buffer Redis de 100 entrées par profil.
    """

    MAX_ENTRIES = 100
    TTL         = 30 * 24 * 3600  # 30 jours

    def __init__(self, cache: CacheService):
        self.cache = cache

    async def log(
        self,
        event_type : str,
        profil_id  : UUID,
        session_id : Optional[str]     = None,
        device_id  : Optional[str]     = None,
        ip_address : Optional[str]     = None,
        details    : Optional[Dict]    = None,
        severity   : str               = "info",
    ) -> None:
        """Enregistre un événement d'audit."""
        entry = {
            "ts"         : datetime.now(timezone.utc).isoformat(),
            "event"      : event_type,
            "profil_id"  : str(profil_id),
            "session_id" : session_id,
            "device_id"  : device_id,
            "ip_address" : ip_address,
            "severity"   : severity,
            "details"    : details or {},
        }

        # Ring buffer Redis
        key      = f"{_PFX_AUDIT}{profil_id}"
        existing = await self.cache.get(key) or []
        existing.append(entry)
        if len(existing) > self.MAX_ENTRIES:
            existing = existing[-self.MAX_ENTRIES:]
        await self.cache.set(key, existing, ttl=self.TTL)

        # Log structuré
        log_fn = logger.warning if severity in ("warning", "critical") else logger.info
        log_fn(
            f"[TOKEN_AUDIT] {event_type} | profil={str(profil_id)[:8]} "
            f"| session={str(session_id or '')[:8]} | ip={ip_address or '?'}"
        )

        # Persister les événements critiques en DB (async, non bloquant)
        if event_type in CRITICAL_EVENTS:
            await self._persist_critical(entry)

    async def get_history(
        self,
        profil_id : UUID,
        limit     : int            = 50,
        event_type: Optional[str]  = None,
    ) -> List[Dict[str, Any]]:
        """Retourne l'historique d'audit pour un profil."""
        key     = f"{_PFX_AUDIT}{profil_id}"
        entries = await self.cache.get(key) or []
        if event_type:
            entries = [e for e in entries if e["event"] == event_type]
        return list(reversed(entries))[:limit]

    async def get_security_events(self, profil_id: UUID) -> List[Dict[str, Any]]:
        """Retourne uniquement les événements de sécurité."""
        return await self.get_history(
            profil_id,
            limit=50,
            event_type=None,
        )

    async def _persist_critical(self, entry: Dict[str, Any]) -> None:
        """Persiste un événement critique dans journal_acces."""
        try:
            from app.database import get_db
            from app.services.audit_service import AuditService
            async for db in get_db():
                audit = AuditService(db)
                await audit.log(
                    type_action = f"token.{entry['event']}",
                    profil_id   = UUID(entry["profil_id"]),
                    module      = "iam.token",
                    ressource   = "session",
                    action      = entry["event"],
                    autorise    = entry["severity"] not in ("warning", "critical"),
                    raison      = str(entry.get("details", {})),
                    ip_address  = entry.get("ip_address"),
                    session_id  = entry.get("session_id"),
                )
                break
        except Exception as e:
            logger.debug(f"Audit DB non critique (ignoré): {e}")
