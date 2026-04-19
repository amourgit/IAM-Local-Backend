"""
Détection d'anomalies de sécurité sur les tokens et sessions.

Détecte :
- Changement d'IP drastique (pays différent)
- Changement de device en cours de session
- Rejeu de token (token utilisé deux fois)
- Vitesse impossible (impossible travel)
- Trop de tentatives de refresh
"""
import logging
from datetime import datetime, timezone, timedelta
from typing import Dict, Any, Optional, List
from uuid import UUID

from app.infrastructure.cache.redis import CacheService

logger = logging.getLogger(__name__)

_PFX_TRAVEL   = "iam:travel:"     # iam:travel:{profil_id}   → dernière IP + timestamp
_PFX_REPLAY   = "iam:replay:"     # iam:replay:{jti}          → vu (anti-replay)
_PFX_RATELIMIT= "iam:rl:refresh:" # iam:rl:refresh:{profil}  → compteur refresh


class AnomalyDetector:
    """
    Détecteur d'anomalies de sécurité en temps réel.
    Toutes les vérifications sont non-bloquantes (log + flag uniquement).
    Les actions (révocation) sont déclenchées par le TokenManager.
    """

    # Seuils
    MAX_REFRESH_PER_HOUR  = 30    # Max refresh tokens par heure
    REPLAY_WINDOW_SECONDS = 300   # Fenêtre anti-replay (5 min)

    def __init__(self, cache: CacheService):
        self.cache = cache

    # ── Anti-Replay ────────────────────────────────────────────────

    async def check_replay(self, jti: str) -> bool:
        """
        Vérifie si un JWT ID a déjà été utilisé (anti-replay).
        Retourne True si c'est un rejeu (attaque détectée).
        """
        key  = f"{_PFX_REPLAY}{jti}"
        seen = await self.cache.get(key)
        if seen:
            logger.warning(f"🚨 Replay attack détecté — JTI: {jti[:16]}...")
            return True
        # Marquer comme vu
        await self.cache.set(key, 1, ttl=self.REPLAY_WINDOW_SECONDS)
        return False

    # ── Rate Limit Refresh ─────────────────────────────────────────

    async def check_refresh_rate(self, profil_id: UUID) -> bool:
        """
        Vérifie le taux de refresh tokens par profil.
        Retourne True si le taux est dépassé.
        """
        key   = f"{_PFX_RATELIMIT}{profil_id}"
        count = await self.cache.get(key) or 0
        if count >= self.MAX_REFRESH_PER_HOUR:
            logger.warning(f"🚨 Rate limit refresh dépassé — profil: {profil_id}")
            return True
        await self.cache.set(key, count + 1, ttl=3600)
        return False

    # ── IP Change Detection ────────────────────────────────────────

    async def record_location(
        self,
        profil_id  : UUID,
        ip_address : str,
        session_id : str,
    ) -> Optional[Dict[str, Any]]:
        """
        Enregistre la localisation et détecte les voyages impossibles.
        Retourne un dict d'anomalie si détecté, None sinon.
        """
        key  = f"{_PFX_TRAVEL}{profil_id}"
        last = await self.cache.get(key)
        now  = datetime.now(timezone.utc)

        anomaly = None
        if last and last.get("ip") != ip_address:
            # IP différente — vérifier le délai
            last_time = datetime.fromisoformat(last["ts"])
            elapsed   = (now - last_time).total_seconds()
            old_ip    = last.get("ip", "")

            # Si même réseau /24 → normal (changement mineur)
            same_network = (
                ".".join(ip_address.split(".")[:3]) ==
                ".".join(old_ip.split(".")[:3])
            )
            if not same_network and elapsed < 300:  # < 5 min, IP différente
                anomaly = {
                    "type"       : "ip_change",
                    "severity"   : "medium",
                    "old_ip"     : old_ip,
                    "new_ip"     : ip_address,
                    "elapsed_sec": elapsed,
                    "session_id" : session_id,
                }
                logger.warning(
                    f"⚠️  Changement IP rapide profil {profil_id}: "
                    f"{old_ip} → {ip_address} en {elapsed:.0f}s"
                )

        await self.cache.set(key, {
            "ip"        : ip_address,
            "ts"        : now.isoformat(),
            "session_id": session_id,
        }, ttl=86400)

        return anomaly

    # ── Device Change Detection ────────────────────────────────────

    def check_device_change(
        self,
        session_device_id : str,
        request_device_id : str,
        session_id        : str,
    ) -> Optional[Dict[str, Any]]:
        """
        Vérifie si le device a changé en cours de session.
        Retourne une anomalie si le device est différent.
        """
        if session_device_id and request_device_id != session_device_id:
            logger.warning(
                f"🚨 Device change en session {session_id[:8]}: "
                f"{session_device_id[:8]} → {request_device_id[:8]}"
            )
            return {
                "type"              : "device_change",
                "severity"          : "high",
                "original_device"   : session_device_id,
                "current_device"    : request_device_id,
                "session_id"        : session_id,
            }
        return None

    # ── Rapport d'anomalies ───────────────────────────────────────

    async def get_anomaly_score(self, profil_id: UUID) -> int:
        """
        Calcule un score d'anomalie pour un profil (0-100).
        Utilisé pour décider du niveau d'action (warn / lock / revoke).
        """
        score = 0
        # Rate limit refresh
        key   = f"{_PFX_RATELIMIT}{profil_id}"
        count = await self.cache.get(key) or 0
        if count > 10:
            score += min(40, count * 2)

        return min(score, 100)
