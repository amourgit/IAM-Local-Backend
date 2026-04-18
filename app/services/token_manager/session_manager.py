"""
Service de gestion des sessions utilisateur.
Gère le cycle de vie des sessions et leur persistance.
"""

import logging
import uuid
from datetime import datetime, timedelta
from typing import Dict, Any, List, Optional
from uuid import UUID

from app.infrastructure.cache.redis import CacheService
from app.config import settings

logger = logging.getLogger(__name__)


class SessionManager:
    """
    Gestionnaire des sessions utilisateur.
    Stockage en cache Redis avec métadonnées complètes.
    """

    def __init__(self, cache: CacheService):
        self.cache = cache
        self.session_ttl_hours = settings.SESSION_TTL_HOURS
        self.max_sessions_per_user = settings.MAX_SESSIONS_PER_USER

    async def create_session(
        self,
        user_id: UUID,
        user_agent: Optional[str] = None,
        ip_address: Optional[str] = None,
        metadata: Dict[str, Any] = None,
        device_info: Dict[str, Any] = None,
        location: Optional[str] = None
    ) -> UUID:
        """
        Crée une nouvelle session utilisateur.

        Args:
            user_id: ID de l'utilisateur
            user_agent: User-Agent du client
            ip_address: Adresse IP du client
            metadata: Métadonnées additionnelles
            device_info: Informations sur le device
            location: Localisation du client

        Returns:
            UUID de la session créée
        """
        session_id = uuid.uuid4()

        session_data = {
            "id": str(session_id),
            "user_id": str(user_id),
            "status": "active",
            "created_at": datetime.utcnow().isoformat(),
            "last_activity": datetime.utcnow().isoformat(),
            "expires_at": (datetime.utcnow() + timedelta(hours=self.session_ttl_hours)).isoformat(),
            "user_agent": user_agent,
            "ip_address": ip_address,
            "device_info": device_info or {},
            "location": location,
            "metadata": metadata or {},
            "activity_count": 0,
            "version": "1.0"
        }

        # Clé de stockage
        cache_key = f"session:{session_id}"

        # TTL en secondes
        ttl_seconds = self.session_ttl_hours * 60 * 60

        await self.cache.set(cache_key, session_data, ttl_seconds=ttl_seconds)

        # Gestion du nombre maximum de sessions par utilisateur
        await self._enforce_max_sessions(user_id)

        logger.info(f"Session créée: {session_id} pour user {user_id}")
        return session_id

    async def get_session(self, session_id: UUID) -> Optional[Dict[str, Any]]:
        """
        Récupère les données d'une session.

        Returns:
            Données de session ou None si inexistante/expirée
        """
        cache_key = f"session:{session_id}"
        session_data = await self.cache.get(cache_key)

        if session_data:
            # Mise à jour de la dernière activité
            await self._update_last_activity(session_id)
            return session_data

        return None

    async def update_session_activity(self, session_id: UUID) -> None:
        """
        Met à jour la dernière activité d'une session.
        Prolonge automatiquement la durée de vie.
        """
        await self._update_last_activity(session_id)

    async def revoke_session(self, session_id: UUID) -> None:
        """
        Marque une session comme révoquée.
        La suppression physique sera faite par le garbage collector.
        """
        cache_key = f"session:{session_id}"
        session_data = await self.cache.get(cache_key)

        if session_data:
            session_data["status"] = "revoked"
            session_data["revoked_at"] = datetime.utcnow().isoformat()

            # Remettre en cache avec TTL courte (5 minutes)
            await self.cache.set(cache_key, session_data, ttl_seconds=300)

            logger.info(f"Session révoquée: {session_id}")

    async def get_user_sessions(self, user_id: UUID) -> List[Dict[str, Any]]:
        """
        Récupère toutes les sessions actives d'un utilisateur.
        """
        try:
            # Recherche de toutes les sessions (coûteux en production)
            # En production, maintenir un index séparé
            pattern = "session:*"
            all_keys = await self.cache.keys(pattern)

            user_sessions = []
            for key in all_keys:
                session_data = await self.cache.get(key)
                if (session_data and
                    session_data.get("user_id") == str(user_id) and
                    session_data.get("status") == "active"):
                    user_sessions.append(session_data)

            return user_sessions

        except Exception as e:
            logger.error(f"Erreur récupération sessions user {user_id}: {str(e)}")
            return []

    async def revoke_user_sessions(self, user_id: UUID) -> int:
        """
        Révoque toutes les sessions d'un utilisateur.
        Returns: nombre de sessions révoquées
        """
        sessions = await self.get_user_sessions(user_id)
        revoked_count = 0

        for session in sessions:
            session_id = UUID(session["id"])
            await self.revoke_session(session_id)
            revoked_count += 1

        logger.info(f"{revoked_count} sessions révoquées pour user {user_id}")
        return revoked_count

    async def cleanup_expired_sessions(self) -> int:
        """
        Nettoie les sessions expirées.
        Normalement géré par Redis TTL, mais méthode présente pour cohérence.
        """
        # Redis gère automatiquement via TTL
        return 0

    # ── Métriques et Monitoring ──────────────────────────────────────

    async def count_active_sessions(self) -> int:
        """
        Compte le nombre total de sessions actives.
        """
        try:
            pattern = "session:*"
            all_keys = await self.cache.keys(pattern)

            active_count = 0
            for key in all_keys:
                session_data = await self.cache.get(key)
                if (session_data and
                    session_data.get("status") == "active"):
                    active_count += 1

            return active_count

        except Exception as e:
            logger.error(f"Erreur comptage sessions: {str(e)}")
            return 0

    async def get_session_stats(self) -> Dict[str, Any]:
        """
        Statistiques détaillées sur les sessions.
        """
        try:
            pattern = "session:*"
            all_keys = await self.cache.keys(pattern)

            stats = {
                "total_keys": len(all_keys),
                "active": 0,
                "revoked": 0,
                "by_user_agent": {},
                "by_ip": {},
                "oldest_session": None,
                "newest_session": None
            }

            oldest_time = datetime.max
            newest_time = datetime.min

            for key in all_keys:
                session_data = await self.cache.get(key)
                if not session_data:
                    continue

                status = session_data.get("status", "unknown")
                if status == "active":
                    stats["active"] += 1
                elif status == "revoked":
                    stats["revoked"] += 1

                # Statistiques par user agent
                ua = session_data.get("user_agent", "unknown")
                stats["by_user_agent"][ua] = stats["by_user_agent"].get(ua, 0) + 1

                # Statistiques par IP
                ip = session_data.get("ip_address", "unknown")
                stats["by_ip"][ip] = stats["by_ip"].get(ip, 0) + 1

                # Sessions les plus anciennes/récentes
                created_at = datetime.fromisoformat(session_data.get("created_at", datetime.max.isoformat()))
                if created_at < oldest_time:
                    oldest_time = created_at
                    stats["oldest_session"] = session_data
                if created_at > newest_time:
                    newest_time = created_at
                    stats["newest_session"] = session_data

            stats["timestamp"] = datetime.utcnow().isoformat()
            return stats

        except Exception as e:
            logger.error(f"Erreur statistiques sessions: {str(e)}")
            return {"error": str(e)}

    # ── Utilitaires Privés ───────────────────────────────────────────

    async def _update_last_activity(self, session_id: UUID) -> None:
        """
        Met à jour la dernière activité d'une session.
        Prolonge automatiquement la durée de vie si nécessaire.
        """
        try:
            cache_key = f"session:{session_id}"
            session_data = await self.cache.get(cache_key)

            if session_data:
                now = datetime.utcnow()
                session_data["last_activity"] = now.isoformat()
                session_data["activity_count"] = session_data.get("activity_count", 0) + 1

                # Prolongation automatique si activité récente
                expires_at = datetime.fromisoformat(session_data["expires_at"])
                if (expires_at - now).total_seconds() < 3600:  # Moins d'1h restante
                    new_expires = now + timedelta(hours=self.session_ttl_hours)
                    session_data["expires_at"] = new_expires.isoformat()

                    # Remettre en cache avec nouvelle TTL
                    ttl_seconds = int((new_expires - now).total_seconds())
                    await self.cache.set(cache_key, session_data, ttl_seconds=ttl_seconds)

                    logger.debug(f"Session {session_id} prolongée jusqu'à {new_expires}")

        except Exception as e:
            logger.warning(f"Erreur mise à jour activité session {session_id}: {str(e)}")

    async def _enforce_max_sessions(self, user_id: UUID) -> None:
        """
        S'assure qu'un utilisateur n'a pas plus de sessions que le maximum autorisé.
        Révoque les sessions les plus anciennes si nécessaire.
        """
        if self.max_sessions_per_user <= 0:
            return  # Pas de limite

        user_sessions = await self.get_user_sessions(user_id)

        if len(user_sessions) > self.max_sessions_per_user:
            # Trier par date de création (plus ancienne en premier)
            sorted_sessions = sorted(
                user_sessions,
                key=lambda s: s.get("created_at", datetime.max.isoformat())
            )

            # Nombre de sessions à révoquer
            to_revoke = len(user_sessions) - self.max_sessions_per_user

            for i in range(to_revoke):
                session_id = UUID(sorted_sessions[i]["id"])
                await self.revoke_session(session_id)

                logger.info(f"Session ancienne révoquée pour user {user_id} (limite: {self.max_sessions_per_user})")

    # ── Sessions Spéciales ───────────────────────────────────────────

    async def create_bootstrap_session(self, admin_user_id: UUID) -> UUID:
        """
        Crée une session spéciale pour l'administrateur bootstrap.
        Cette session a des propriétés spéciales.
        """
        return await self.create_session(
            user_id=admin_user_id,
            user_agent="bootstrap-system",
            ip_address="127.0.0.1",
            metadata={
                "type": "bootstrap",
                "temporary": True,
                "auto_cleanup": True
            }
        )

    async def is_bootstrap_session(self, session_id: UUID) -> bool:
        """
        Vérifie si une session est de type bootstrap.
        """
        session = await self.get_session(session_id)
        if session:
            metadata = session.get("metadata", {})
            return metadata.get("type") == "bootstrap"
        return False

    async def get_all_sessions(self) -> list:
        """Récupère toutes les sessions actives."""
        try:
            all_keys = await self.cache.keys("session:*")
            sessions = []
            for key in all_keys:
                data = await self.cache.get(key)
                if data:
                    sessions.append(data)
            return sessions
        except Exception as e:
            logger.error(f"Erreur get_all_sessions: {e}")
            return []