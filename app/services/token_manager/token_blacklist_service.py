"""
Service de blacklist des tokens et sessions.
Gère la révocation immédiate des tokens compromis ou expirés.
"""

import logging
from datetime import datetime, timedelta
from typing import Dict, Any, Optional
from uuid import UUID

from app.infrastructure.cache.redis import CacheService
from app.config import settings

logger = logging.getLogger(__name__)


class TokenBlacklistService:
    """
    Service de gestion de la blacklist des tokens et sessions.
    Permet la révocation immédiate et le contrôle d'accès.
    """

    def __init__(self, cache: CacheService):
        self.cache = cache
        self.default_ttl_minutes = settings.SESSION_BLACKLIST_TTL_MINUTES

    async def blacklist_session(
        self,
        session_id: str,
        reason: str = "manual",
        ttl_minutes: Optional[int] = None
    ) -> None:
        """
        Ajoute une session à la blacklist.

        Args:
            session_id: ID de la session à blacklister
            reason: Raison de la blacklist
            ttl_minutes: Durée de vie en minutes (défaut: config)
        """
        ttl = ttl_minutes or self.default_ttl_minutes
        ttl_seconds = ttl * 60

        blacklist_entry = {
            "session_id": session_id,
            "reason": reason,
            "blacklisted_at": datetime.utcnow().isoformat(),
            "ttl_minutes": ttl,
            "expires_at": (datetime.utcnow() + timedelta(minutes=ttl)).isoformat()
        }

        cache_key = f"blacklist:session:{session_id}"
        await self.cache.set(cache_key, blacklist_entry, ttl_seconds=ttl_seconds)

        logger.info(f"Session {session_id} blacklisted: {reason} (TTL: {ttl}min)")

    async def blacklist_user(
        self,
        user_id: UUID,
        reason: str = "user_suspended",
        ttl_minutes: Optional[int] = None
    ) -> None:
        """
        Blacklist toutes les sessions d'un utilisateur.
        Utile pour suspension de compte.
        """
        ttl = ttl_minutes or self.default_ttl_minutes
        ttl_seconds = ttl * 60

        blacklist_entry = {
            "user_id": str(user_id),
            "reason": reason,
            "blacklisted_at": datetime.utcnow().isoformat(),
            "ttl_minutes": ttl,
            "expires_at": (datetime.utcnow() + timedelta(minutes=ttl)).isoformat(),
            "type": "user_blacklist"
        }

        cache_key = f"blacklist:user:{user_id}"
        await self.cache.set(cache_key, blacklist_entry, ttl_seconds=ttl_seconds)

        logger.info(f"User {user_id} blacklisted: {reason} (TTL: {ttl}min)")

    async def blacklist_token(
        self,
        token_jti: str,
        reason: str = "token_compromised",
        ttl_minutes: Optional[int] = None
    ) -> None:
        """
        Blacklist un token spécifique par son JTI.

        Args:
            token_jti: JWT ID (jti) du token
            reason: Raison de la blacklist
            ttl_minutes: Durée de vie
        """
        ttl = ttl_minutes or self.default_ttl_minutes
        ttl_seconds = ttl * 60

        blacklist_entry = {
            "token_jti": token_jti,
            "reason": reason,
            "blacklisted_at": datetime.utcnow().isoformat(),
            "ttl_minutes": ttl,
            "expires_at": (datetime.utcnow() + timedelta(minutes=ttl)).isoformat(),
            "type": "token_blacklist"
        }

        cache_key = f"blacklist:token:{token_jti}"
        await self.cache.set(cache_key, blacklist_entry, ttl_seconds=ttl_seconds)

        logger.info(f"Token {token_jti} blacklisted: {reason} (TTL: {ttl}min)")

    async def is_blacklisted(self, identifier: str) -> bool:
        """
        Vérifie si un identifiant est blacklisted.
        L'identifiant peut être un session_id, user_id, ou token_jti.

        Args:
            identifier: ID à vérifier (session, user, ou token JTI)

        Returns:
            True si blacklisted, False sinon
        """
        # Vérification session
        session_key = f"blacklist:session:{identifier}"
        if await self.cache.exists(session_key):
            return True

        # Vérification user (pour les contrôles d'accès utilisateur)
        user_key = f"blacklist:user:{identifier}"
        if await self.cache.exists(user_key):
            return True

        # Vérification token spécifique
        token_key = f"blacklist:token:{identifier}"
        if await self.cache.exists(token_key):
            return True

        return False

    async def get_blacklist_info(self, identifier: str) -> Optional[Dict[str, Any]]:
        """
        Récupère les informations de blacklist pour un identifiant.
        """
        # Essai dans l'ordre: session, user, token
        keys = [
            f"blacklist:session:{identifier}",
            f"blacklist:user:{identifier}",
            f"blacklist:token:{identifier}"
        ]

        for key in keys:
            data = await self.cache.get(key)
            if data:
                return data

        return None

    async def remove_from_blacklist(self, identifier: str) -> bool:
        """
        Retire un identifiant de la blacklist.
        Returns: True si retiré, False s'il n'était pas blacklisté
        """
        removed = False

        keys = [
            f"blacklist:session:{identifier}",
            f"blacklist:user:{identifier}",
            f"blacklist:token:{identifier}"
        ]

        for key in keys:
            if await self.cache.exists(key):
                await self.cache.delete(key)
                removed = True
                logger.info(f"Retiré de blacklist: {key}")

        return removed

    async def extend_blacklist(
        self,
        identifier: str,
        additional_minutes: int
    ) -> bool:
        """
        Prolonge la durée de blacklist d'un identifiant.
        Returns: True si prolongé, False si pas trouvé
        """
        info = await self.get_blacklist_info(identifier)
        if not info:
            return False

        # Calcul de la nouvelle durée
        blacklisted_at = datetime.fromisoformat(info["blacklisted_at"])
        current_ttl = info["ttl_minutes"]
        new_ttl = current_ttl + additional_minutes

        # Reconstruction de l'entrée avec nouvelle TTL
        info["ttl_minutes"] = new_ttl
        info["expires_at"] = (blacklisted_at + timedelta(minutes=new_ttl)).isoformat()
        info["extended_at"] = datetime.utcnow().isoformat()

        # Remise en cache avec nouvelle TTL
        ttl_seconds = new_ttl * 60

        # Détermination du type de clé
        if "session_id" in info:
            cache_key = f"blacklist:session:{identifier}"
        elif "user_id" in info:
            cache_key = f"blacklist:user:{identifier}"
        else:
            cache_key = f"blacklist:token:{identifier}"

        await self.cache.set(cache_key, info, ttl_seconds=ttl_seconds)

        logger.info(f"Blacklist prolongée pour {identifier}: +{additional_minutes}min (total: {new_ttl}min)")
        return True

    # ── Gestion de Crise ─────────────────────────────────────────────

    async def emergency_blacklist_all(self, reason: str = "emergency") -> Dict[str, int]:
        """
        Blacklist d'urgence de TOUTES les sessions actives.
        Utile en cas de compromission massive.

        Returns: statistiques de l'opération
        """
        # Cette méthode nécessiterait une liste de toutes les sessions actives
        # Pour l'instant, on retourne un avertissement
        logger.critical("BLACKLIST D'URGENCE DÉCLENCHÉE - IMPLEMENTATION REQUISE")

        return {
            "sessions_blacklisted": 0,
            "users_affected": 0,
            "warning": "Méthode non implémentée complètement"
        }

    # ── Métriques et Monitoring ──────────────────────────────────────

    async def count_blacklisted(self) -> Dict[str, int]:
        """
        Compte les éléments blacklisted par type.
        """
        try:
            # Comptage approximatif (Redis ne permet pas de compter facilement par pattern)
            # En production, utiliser des clés dédiées pour les compteurs
            session_pattern = "blacklist:session:*"
            user_pattern = "blacklist:user:*"
            token_pattern = "blacklist:token:*"

            session_keys = await self.cache.keys(session_pattern)
            user_keys = await self.cache.keys(user_pattern)
            token_keys = await self.cache.keys(token_pattern)

            return {
                "sessions": len(session_keys),
                "users": len(user_keys),
                "tokens": len(token_keys),
                "total": len(session_keys) + len(user_keys) + len(token_keys)
            }

        except Exception as e:
            logger.error(f"Erreur comptage blacklist: {str(e)}")
            return {"error": str(e)}

    async def get_blacklist_summary(self) -> Dict[str, Any]:
        """
        Résumé détaillé de la blacklist.
        """
        counts = await self.count_blacklisted()

        return {
            "counts": counts,
            "timestamp": datetime.utcnow().isoformat(),
            "default_ttl_minutes": self.default_ttl_minutes
        }

    async def cleanup_expired_entries(self) -> int:
        """
        Nettoie les entrées expirées de la blacklist.
        Normalement géré automatiquement par Redis TTL.

        Returns: nombre d'entrées nettoyées (toujours 0 en pratique)
        """
        # Redis gère automatiquement l'expiration via TTL
        # Cette méthode est présente pour cohérence d'interface
        return 0