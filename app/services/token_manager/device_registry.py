"""
Registre des devices par profil.

Un device = un navigateur/app sur un appareil physique.
Identifié par un fingerprint déterministe basé sur User-Agent + IP.
Un profil peut avoir N devices actifs (max configuré).
Chaque device ne peut avoir qu'UNE session active à la fois.
"""
import hashlib
import logging
from datetime import datetime, timezone
from typing import Dict, Any, List, Optional
from uuid import UUID

from app.infrastructure.cache.redis import CacheService

logger = logging.getLogger(__name__)

# Préfixes Redis
_PFX_DEVICE   = "iam:device:"        # iam:device:{device_id}       → device data
_PFX_PROFIL   = "iam:profil:devices:" # iam:profil:devices:{profil}  → set of device_ids
_PFX_SESSION  = "iam:device:session:" # iam:device:session:{device}  → session_id actif


def fingerprint(user_agent: str, ip_address: str = "") -> str:
    """
    Génère un fingerprint déterministe pour identifier un device.
    Basé sur : User-Agent + (optionnel) réseau /24.
    Stable même si l'IP change dans le même /24.
    """
    # Tronquer l'IP au /24 pour tolérer les changements mineurs
    network = ".".join(ip_address.split(".")[:3]) if ip_address else ""
    raw = f"{user_agent}|{network}"
    return hashlib.sha256(raw.encode()).hexdigest()[:32]


class DeviceRegistry:
    """
    Registre Redis des devices par profil.
    TTL 90 jours (refresh à chaque connexion).
    """

    DEVICE_TTL     = 90 * 24 * 3600   # 90 jours
    MAX_DEVICES    = 10                # Max devices par profil

    def __init__(self, cache: CacheService):
        self.cache = cache

    # ── Enregistrement ─────────────────────────────────────────────

    async def register(
        self,
        profil_id  : UUID,
        device_id  : str,
        device_info: Dict[str, Any],
        ip_address : str,
        user_agent : str,
    ) -> Dict[str, Any]:
        """Enregistre ou met à jour un device pour un profil."""
        now = datetime.now(timezone.utc).isoformat()
        key = f"{_PFX_DEVICE}{device_id}"

        existing = await self.cache.get(key)
        if existing:
            existing["last_seen"]     = now
            existing["ip_address"]    = ip_address
            existing["login_count"]   = existing.get("login_count", 0) + 1
            device_data = existing
        else:
            device_data = {
                "device_id"    : device_id,
                "profil_id"    : str(profil_id),
                "first_seen"   : now,
                "last_seen"    : now,
                "ip_address"   : ip_address,
                "user_agent"   : user_agent,
                "login_count"  : 1,
                "trusted"      : False,
                **device_info,
            }

        await self.cache.set(key, device_data, ttl=self.DEVICE_TTL)

        # Ajouter à l'index du profil
        set_key = f"{_PFX_PROFIL}{profil_id}"
        device_set = await self.cache.get(set_key) or []
        if device_id not in device_set:
            device_set.append(device_id)
            # Limiter le nombre de devices
            if len(device_set) > self.MAX_DEVICES:
                oldest = device_set.pop(0)
                await self.cache.delete(f"{_PFX_DEVICE}{oldest}")
                await self.cache.delete(f"{_PFX_SESSION}{oldest}")
        await self.cache.set(set_key, device_set, ttl=self.DEVICE_TTL)

        logger.debug(f"Device {device_id[:8]}... enregistré pour profil {profil_id}")
        return device_data

    # ── Session active par device ──────────────────────────────────

    async def set_active_session(self, device_id: str, session_id: str) -> None:
        """Lie une session active à un device (1 session max par device)."""
        key = f"{_PFX_SESSION}{device_id}"
        await self.cache.set(key, session_id, ttl=self.DEVICE_TTL)

    async def get_active_session(self, device_id: str) -> Optional[str]:
        """Retourne l'ID de session actif pour un device."""
        return await self.cache.get(f"{_PFX_SESSION}{device_id}")

    async def clear_active_session(self, device_id: str) -> None:
        """Supprime la session active d'un device (déconnexion)."""
        await self.cache.delete(f"{_PFX_SESSION}{device_id}")

    # ── Consultation ───────────────────────────────────────────────

    async def get_device(self, device_id: str) -> Optional[Dict[str, Any]]:
        return await self.cache.get(f"{_PFX_DEVICE}{device_id}")

    async def get_profil_devices(self, profil_id: UUID) -> List[Dict[str, Any]]:
        """Retourne tous les devices connus d'un profil."""
        set_key  = f"{_PFX_PROFIL}{profil_id}"
        device_ids = await self.cache.get(set_key) or []
        devices    = []
        for did in device_ids:
            d = await self.cache.get(f"{_PFX_DEVICE}{did}")
            if d:
                # Enrichir avec la session active
                d["has_active_session"] = bool(await self.get_active_session(did))
                devices.append(d)
        return devices

    async def count_active_devices(self, profil_id: UUID) -> int:
        """Nombre de devices avec une session active."""
        devices = await self.get_profil_devices(profil_id)
        return sum(1 for d in devices if d.get("has_active_session"))

    # ── Trust ──────────────────────────────────────────────────────

    async def trust_device(self, device_id: str) -> bool:
        """Marque un device comme de confiance (MFA validé)."""
        key  = f"{_PFX_DEVICE}{device_id}"
        data = await self.cache.get(key)
        if not data:
            return False
        data["trusted"]    = True
        data["trusted_at"] = datetime.now(timezone.utc).isoformat()
        await self.cache.set(key, data, ttl=self.DEVICE_TTL)
        return True

    # ── Révocation ─────────────────────────────────────────────────

    async def revoke_device(self, device_id: str, profil_id: UUID) -> None:
        """Révoque un device et supprime sa session active."""
        await self.cache.delete(f"{_PFX_DEVICE}{device_id}")
        await self.cache.delete(f"{_PFX_SESSION}{device_id}")
        # Retirer de l'index du profil
        set_key    = f"{_PFX_PROFIL}{profil_id}"
        device_set = await self.cache.get(set_key) or []
        if device_id in device_set:
            device_set.remove(device_id)
            await self.cache.set(set_key, device_set, ttl=self.DEVICE_TTL)

    async def revoke_all_devices(self, profil_id: UUID) -> int:
        """Révoque tous les devices d'un profil (déconnexion totale)."""
        set_key    = f"{_PFX_PROFIL}{profil_id}"
        device_ids = await self.cache.get(set_key) or []
        for did in device_ids:
            await self.cache.delete(f"{_PFX_DEVICE}{did}")
            await self.cache.delete(f"{_PFX_SESSION}{did}")
        await self.cache.delete(set_key)
        logger.info(f"{len(device_ids)} devices révoqués pour profil {profil_id}")
        return len(device_ids)
