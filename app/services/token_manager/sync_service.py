"""
Service de synchronisation avec IAM Central.
Gère la récupération des informations utilisateur et la vérification des statuts.
"""

import httpx
import logging
from datetime import datetime, timedelta
from typing import Dict, Any, Optional

from app.config import settings
from app.infrastructure.cache.redis import CacheService

logger = logging.getLogger(__name__)


class SyncService:
    """
    Service de synchronisation avec IAM Central.
    Gère la communication sécurisée et la mise en cache des données.
    """

    def __init__(self, cache: Optional[CacheService] = None):
        self.cache = cache or CacheService()
        self.iam_central_url = settings.IAM_CENTRAL_URL
        self.iam_central_enabled = settings.IAM_CENTRAL_ENABLED
        self.sync_timeout = settings.IAM_CENTRAL_SYNC_TIMEOUT_SECONDS
        self.cache_ttl_minutes = settings.IAM_CENTRAL_CACHE_TTL_MINUTES

        # Client HTTP réutilisable
        self.http_client = httpx.AsyncClient(
            timeout=self.sync_timeout,
            headers={
                "User-Agent": "IAM-Local-Sync/1.0",
                "Accept": "application/json"
            }
        )

    async def get_user_from_iam_central(self, user_id_national: str) -> Optional[Dict[str, Any]]:
        """
        Récupère les informations d'un utilisateur depuis IAM Central.

        Args:
            user_id_national: ID national de l'utilisateur

        Returns:
            Données utilisateur ou None si non trouvé
        """
        if not self.iam_central_enabled:
            logger.debug("IAM Central désactivé, pas de synchronisation")
            return None

        # Vérification cache
        cache_key = f"iam_central:user:{user_id_national}"
        cached_data = await self.cache.get(cache_key)

        if cached_data:
            logger.debug(f"Données utilisateur {user_id_national} récupérées du cache")
            return cached_data

        # Appel à IAM Central
        try:
            url = f"{self.iam_central_url}/api/v1/users/{user_id_national}"
            response = await self.http_client.get(url)

            if response.status_code == 200:
                user_data = response.json()

                # Mise en cache
                await self.cache.set(
                    cache_key,
                    user_data,
                    ttl_seconds=self.cache_ttl_minutes * 60
                )

                logger.info(f"Utilisateur {user_id_national} synchronisé depuis IAM Central")
                return user_data

            elif response.status_code == 404:
                logger.info(f"Utilisateur {user_id_national} non trouvé dans IAM Central")
                return None

            else:
                logger.warning(f"Erreur IAM Central: {response.status_code} - {response.text}")
                return None

        except httpx.RequestError as e:
            logger.error(f"Erreur réseau IAM Central: {str(e)}")
            return None
        except Exception as e:
            logger.error(f"Erreur inattendue synchronisation IAM Central: {str(e)}")
            return None

    async def check_user_status(self, user_id_national: str) -> Dict[str, Any]:
        """
        Vérifie le statut d'un utilisateur dans IAM Central.

        Returns:
            {
                "status": "active|suspended|revoked|unknown",
                "reason": "Raison de la suspension (optionnel)",
                "last_check": "2024-01-01T12:00:00Z"
            }
        """
        if not self.iam_central_enabled:
            return {
                "status": "active",
                "reason": None,
                "last_check": datetime.utcnow().isoformat()
            }

        # Vérification cache
        cache_key = f"iam_central:status:{user_id_national}"
        cached_status = await self.cache.get(cache_key)

        if cached_status:
            return cached_status

        # Appel à IAM Central
        try:
            url = f"{self.iam_central_url}/api/v1/users/{user_id_national}/status"
            response = await self.http_client.get(url)

            status_data = {
                "status": "unknown",
                "reason": None,
                "last_check": datetime.utcnow().isoformat()
            }

            if response.status_code == 200:
                api_response = response.json()
                status_data.update(api_response)

            elif response.status_code == 404:
                status_data["status"] = "not_found"

            else:
                logger.warning(f"Erreur vérification statut IAM Central: {response.status_code}")

            # Mise en cache (TTL court pour les statuts)
            await self.cache.set(
                cache_key,
                status_data,
                ttl_seconds=300  # 5 minutes
            )

            return status_data

        except Exception as e:
            logger.error(f"Erreur vérification statut IAM Central: {str(e)}")
            return {
                "status": "unknown",
                "reason": f"Erreur de vérification: {str(e)}",
                "last_check": datetime.utcnow().isoformat()
            }

    async def get_users_batch(self, user_ids: list) -> Dict[str, Any]:
        """
        Récupère les informations de plusieurs utilisateurs en batch.
        Optimisé pour réduire les appels API.
        """
        if not self.iam_central_enabled:
            return {"users": {}, "not_found": user_ids}

        try:
            url = f"{self.iam_central_url}/api/v1/users/batch"
            response = await self.http_client.post(
                url,
                json={"user_ids": user_ids}
            )

            if response.status_code == 200:
                batch_data = response.json()

                # Mise en cache individuelle
                for user_id, user_data in batch_data.get("users", {}).items():
                    cache_key = f"iam_central:user:{user_id}"
                    await self.cache.set(
                        cache_key,
                        user_data,
                        ttl_seconds=self.cache_ttl_minutes * 60
                    )

                logger.info(f"Batch synchronisation: {len(batch_data.get('users', {}))} utilisateurs")
                return batch_data

            else:
                logger.warning(f"Erreur batch IAM Central: {response.status_code}")
                return {"users": {}, "not_found": user_ids}

        except Exception as e:
            logger.error(f"Erreur batch synchronisation IAM Central: {str(e)}")
            return {"users": {}, "not_found": user_ids, "error": str(e)}

    async def invalidate_user_cache(self, user_id_national: str) -> None:
        """
        Invalide le cache d'un utilisateur.
        Utile après mise à jour dans IAM Central.
        """
        cache_keys = [
            f"iam_central:user:{user_id_national}",
            f"iam_central:status:{user_id_national}"
        ]

        for key in cache_keys:
            await self.cache.delete(key)

        logger.info(f"Cache invalidé pour utilisateur {user_id_national}")

    async def get_sync_status(self) -> Dict[str, Any]:
        """
        État général de la synchronisation avec IAM Central.
        """
        if not self.iam_central_enabled:
            return {
                "enabled": False,
                "status": "disabled",
                "message": "Synchronisation IAM Central désactivée"
            }

        try:
            # Test de connectivité
            url = f"{self.iam_central_url}/health"
            response = await self.http_client.get(url, timeout=5)

            return {
                "enabled": True,
                "status": "healthy" if response.status_code == 200 else "unhealthy",
                "iam_central_url": self.iam_central_url,
                "cache_ttl_minutes": self.cache_ttl_minutes,
                "last_check": datetime.utcnow().isoformat(),
                "response_time_ms": response.elapsed.total_seconds() * 1000 if hasattr(response, 'elapsed') else None
            }

        except Exception as e:
            return {
                "enabled": True,
                "status": "error",
                "error": str(e),
                "iam_central_url": self.iam_central_url,
                "last_check": datetime.utcnow().isoformat()
            }

    # ── Gestion des Webhooks (Optionnel) ─────────────────────────────

    async def register_webhook(self) -> Optional[str]:
        """
        Enregistre un webhook auprès d'IAM Central pour recevoir
        les notifications de changement en temps réel.
        """
        if not self.iam_central_enabled:
            return None

        try:
            # URL du webhook local (à configurer)
            webhook_url = f"{settings.APP_URL}/api/v1/webhooks/iam-central"

            url = f"{self.iam_central_url}/api/v1/webhooks/register"
            response = await self.http_client.post(
                url,
                json={
                    "url": webhook_url,
                    "events": ["user.updated", "user.suspended", "user.revoked"],
                    "secret": settings.WEBHOOK_SECRET
                }
            )

            if response.status_code == 201:
                webhook_data = response.json()
                logger.info(f"Webhook enregistré auprès d'IAM Central: {webhook_data.get('id')}")
                return webhook_data.get("id")

            else:
                logger.warning(f"Échec enregistrement webhook: {response.status_code}")
                return None

        except Exception as e:
            logger.error(f"Erreur enregistrement webhook: {str(e)}")
            return None

    async def handle_webhook_event(self, event_data: Dict[str, Any]) -> None:
        """
        Traite un événement webhook reçu d'IAM Central.
        """
        event_type = event_data.get("type")
        user_id = event_data.get("user_id")

        if event_type in ["user.updated", "user.suspended", "user.revoked"]:
            # Invalidation du cache
            await self.invalidate_user_cache(user_id)

            # Log de l'événement
            logger.info(f"Événement IAM Central traité: {event_type} pour user {user_id}")

            # Ici on pourrait déclencher des actions locales
            # (révocation de sessions, mise à jour de profil, etc.)

    # ── Métriques ────────────────────────────────────────────────────

    async def get_sync_metrics(self) -> Dict[str, Any]:
        """
        Métriques de synchronisation.
        """
        # En production, maintenir des compteurs dans Redis
        return {
            "iam_central_enabled": self.iam_central_enabled,
            "cache_ttl_minutes": self.cache_ttl_minutes,
            "sync_timeout_seconds": self.sync_timeout,
            "cached_users_count": await self._count_cached_users(),
            "last_sync_check": datetime.utcnow().isoformat()
        }

    async def _count_cached_users(self) -> int:
        """
        Compte le nombre d'utilisateurs en cache.
        """
        try:
            pattern = "iam_central:user:*"
            keys = await self.cache.keys(pattern)
            return len(keys)
        except Exception:
            return 0

    # ── Nettoyage ────────────────────────────────────────────────────

    async def cleanup_expired_cache(self) -> int:
        """
        Nettoie les entrées expirées du cache.
        Redis gère normalement l'expiration automatiquement.
        """
        # Méthode présente pour cohérence d'interface
        return 0

    async def __aenter__(self):
        """Context manager pour le client HTTP."""
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Fermeture propre du client HTTP."""
        await self.http_client.aclose()