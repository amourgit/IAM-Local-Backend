"""
Service de gestion des configurations de tokens.
Charge et met à jour dynamiquement les paramètres depuis la base de données.
"""

from typing import Dict, Optional, Any, List
from uuid import UUID
from sqlalchemy.ext.asyncio import AsyncSession
import logging
import time

from app.models.token_models import TokenSettings
from app.repositories.token_config_repository import TokenConfigRepository

logger = logging.getLogger(__name__)


class TokenConfigService:
    """
    Service de gestion des configurations de tokens avec cache.
    Charge et met à jour dynamiquement les paramètres depuis la base de données.
    """

    _instance = None
    _config_cache: Optional[Dict[str, Any]] = None
    _cache_timestamp: float = 0
    _cache_ttl: int = 300  # 5 minutes

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance

    def __init__(self):
        if not hasattr(self, '_initialized'):
            self._initialized = True
            self._config_cache = None
            self._cache_timestamp = 0

    async def _load_config(self, db: AsyncSession) -> Dict[str, Any]:
        try:
            repository = TokenConfigRepository(db)
            active_config = await repository.get_active()

            if active_config:
                config = self._config_from_model(active_config)
                logger.info(f"Configuration chargée depuis la base: ID {active_config.id}")
            else:
                config = self._get_default_config()
                logger.info("Aucune configuration active trouvée, utilisation des valeurs par défaut")

            self._config_cache = config
            self._cache_timestamp = time.time()
            return config

        except Exception as e:
            logger.error(f"Erreur lors du chargement de la configuration: {e}")
            config = self._get_default_config()
            self._config_cache = config
            self._cache_timestamp = time.time()
            return config

    def _config_from_model(self, config: TokenSettings) -> Dict[str, Any]:
        """
        Convertit un modèle TokenSettings en dictionnaire de configuration.
        ✅ Noms alignés avec les colonnes réelles du modèle TokenSettings.
        """
        return {
            # Durées — colonnes: access_token_lifetime, refresh_token_lifetime (en minutes)
            'access_token_lifetime_minutes': config.access_token_lifetime,
            'refresh_token_lifetime_minutes': config.refresh_token_lifetime,
            'refresh_token_lifetime_days': config.refresh_token_lifetime // (24 * 60),

            # Sessions
            'max_sessions_per_user': config.max_sessions_per_user,
            'session_ttl_hours': config.session_ttl_hours,
            'session_timeout_minutes': config.session_ttl_hours * 60,

            # Sécurité tokens
            'rotate_refresh_tokens': config.rotate_refresh_tokens,
            'enable_token_rotation': config.rotate_refresh_tokens,
            'enable_blacklist': config.enable_blacklist,
            'blacklist_ttl_minutes': config.blacklist_ttl_minutes,

            # Validations
            'require_https': config.require_https,
            'enable_ip_validation': config.validate_ip,
            'enable_user_agent_validation': config.validate_user_agent,
            'enable_device_tracking': True,

            # Chiffrement
            'encrypt_tokens': config.encrypt_tokens,

            # Valeurs fixes (pas dans le modèle actuel)
            'jwt_algorithm': 'HS256',
            'jwt_issuer': 'iam-local',
            'max_failed_attempts': 5,
            'lockout_duration_minutes': 15,
            'enable_rate_limiting': True,
            'rate_limit_requests': 100,
            'rate_limit_window_minutes': 15,
        }

    def _get_default_config(self) -> Dict[str, Any]:
        return {
            'access_token_lifetime_minutes': 30,
            'refresh_token_lifetime_minutes': 10080,   # 7 jours
            'refresh_token_lifetime_days': 7,
            'max_sessions_per_user': 5,
            'session_ttl_hours': 24,
            'session_timeout_minutes': 1440,
            'rotate_refresh_tokens': True,
            'enable_token_rotation': True,
            'enable_blacklist': True,
            'blacklist_ttl_minutes': 1440,
            'require_https': False,
            'enable_ip_validation': True,
            'enable_user_agent_validation': True,
            'enable_device_tracking': True,
            'encrypt_tokens': False,
            'jwt_algorithm': 'HS256',
            'jwt_issuer': 'iam-local',
            'max_failed_attempts': 5,
            'lockout_duration_minutes': 15,
            'enable_rate_limiting': True,
            'rate_limit_requests': 100,
            'rate_limit_window_minutes': 15,
        }

    async def get_config(self, db: AsyncSession, force_refresh: bool = False) -> Dict[str, Any]:
        current_time = time.time()

        if (not force_refresh and
            self._config_cache is not None and
            current_time - self._cache_timestamp < self._cache_ttl):
            return self._config_cache

        return await self._load_config(db)

    async def refresh_configuration_cache(self, db: AsyncSession) -> Dict[str, Any]:
        logger.info("Rechargement forcé de la configuration")
        return await self._load_config(db)

    async def get_active_configuration(self, db: AsyncSession) -> Optional[TokenSettings]:
        repository = TokenConfigRepository(db)
        return await repository.get_active()

    async def get_configuration_by_id(self, db: AsyncSession, config_id: UUID) -> Optional[TokenSettings]:
        repository = TokenConfigRepository(db)
        return await repository.get_by_id(config_id)

    async def get_configuration_history(self, db: AsyncSession, skip: int = 0, limit: int = 50) -> List[TokenSettings]:
        repository = TokenConfigRepository(db)
        return await repository.get_all(skip=skip, limit=limit)

    async def create_configuration(self, db: AsyncSession, settings_data: dict, created_by: Optional[UUID] = None) -> TokenSettings:
        repository = TokenConfigRepository(db)
        latest_version = await repository.get_latest_version()
        settings_data['version'] = latest_version + 1
        if created_by:
            settings_data['created_by'] = created_by
            settings_data['updated_by'] = created_by
        config = await repository.create(settings_data)
        if await repository.count() == 1:
            await self._load_config(db)
        return config

    async def update_configuration(self, db: AsyncSession, config_id: UUID, update_data: dict, updated_by: Optional[UUID] = None) -> Optional[TokenSettings]:
        repository = TokenConfigRepository(db)
        if updated_by:
            update_data['updated_by'] = updated_by
        config = await repository.update(config_id, update_data)
        if config and config.is_active:
            await self._load_config(db)
        return config

    async def activate_configuration(self, db: AsyncSession, config_id: UUID, activated_by: Optional[UUID] = None, version_comment: Optional[str] = None) -> tuple:
        repository = TokenConfigRepository(db)
        config = await repository.get_by_id(config_id)
        if not config:
            return False, "Configuration non trouvée", None, None

        current_active = await repository.get_active()
        previous_id = current_active.id if current_active else None
        activated_config = await repository.activate(config_id)

        if activated_config:
            await self._load_config(db)
            message = f"Configuration {config_id} activée avec succès"
            if version_comment:
                message += f" - {version_comment}"
            return True, message, activated_config, previous_id
        else:
            return False, "Erreur lors de l'activation de la configuration", None, None

    async def delete_configuration(self, db: AsyncSession, config_id: UUID, deleted_by: Optional[UUID] = None) -> tuple:
        repository = TokenConfigRepository(db)
        config = await repository.get_by_id(config_id)
        if not config:
            return False, "Configuration non trouvée"
        if config.is_active:
            return False, "Impossible de supprimer une configuration active"
        success = await repository.delete(config_id)
        if success:
            return True, f"Configuration {config_id} supprimée avec succès"
        else:
            return False, "Erreur lors de la suppression de la configuration"

    def is_config_loaded(self) -> bool:
        return self._config_cache is not None

    def get_active_config_name(self) -> str:
        if self._config_cache:
            return "db_config"
        return "default"

    # ── Accesseurs avec db ───────────────────────────────────────────

    async def get_access_token_lifetime_minutes(self, db: AsyncSession) -> int:
        config = await self.get_config(db)
        return config.get('access_token_lifetime_minutes', 30)

    async def get_refresh_token_lifetime_days(self, db: AsyncSession) -> int:
        config = await self.get_config(db)
        return config.get('refresh_token_lifetime_days', 7)

    async def get_refresh_token_lifetime_minutes(self, db: AsyncSession) -> int:
        config = await self.get_config(db)
        return config.get('refresh_token_lifetime_minutes', 10080)

    async def get_max_sessions_per_user(self, db: AsyncSession) -> int:
        config = await self.get_config(db)
        return config.get('max_sessions_per_user', 5)

    async def get_session_timeout_minutes(self, db: AsyncSession) -> int:
        config = await self.get_config(db)
        return config.get('session_timeout_minutes', 1440)

    async def get_enable_ip_validation(self, db: AsyncSession) -> bool:
        config = await self.get_config(db)
        return config.get('enable_ip_validation', True)

    async def get_enable_user_agent_validation(self, db: AsyncSession) -> bool:
        config = await self.get_config(db)
        return config.get('enable_user_agent_validation', True)

    async def get_enable_device_tracking(self, db: AsyncSession) -> bool:
        config = await self.get_config(db)
        return config.get('enable_device_tracking', True)


# Instance globale
_token_config_service = TokenConfigService()


def get_token_config_service() -> TokenConfigService:
    return _token_config_service
