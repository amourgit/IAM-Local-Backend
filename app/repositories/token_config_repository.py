"""
Repository pour la gestion des configurations de tokens.
Gère la persistance des paramètres de sécurité en base de données.
"""

from typing import List, Optional
from uuid import UUID
from sqlalchemy import select, update, desc, and_
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.token_models import TokenSettings


class TokenConfigRepository:
    """
    Repository pour les opérations CRUD sur TokenSettings.
    """

    def __init__(self, db: AsyncSession):
        self.db = db

    async def create(self, config_data: dict) -> TokenSettings:
        """
        Créer une nouvelle configuration.

        Args:
            config_data: Données de la configuration

        Returns:
            TokenSettings: La configuration créée
        """
        config = TokenSettings(**config_data)
        self.db.add(config)
        await self.db.commit()
        await self.db.refresh(config)
        return config

    async def get_by_id(self, config_id: UUID) -> Optional[TokenSettings]:
        """
        Récupérer une configuration par son ID.

        Args:
            config_id: ID de la configuration

        Returns:
            TokenSettings ou None: La configuration trouvée
        """
        stmt = select(TokenSettings).where(TokenSettings.id == config_id)
        result = await self.db.execute(stmt)
        return result.scalar_one_or_none()

    async def get_active(self) -> Optional[TokenSettings]:
        """
        Récupérer la configuration active.

        Returns:
            TokenSettings ou None: La configuration active
        """
        stmt = select(TokenSettings).where(
            TokenSettings.is_active == True
        ).order_by(desc(TokenSettings.created_at))
        result = await self.db.execute(stmt)
        return result.scalar_one_or_none()

    async def get_all(self, skip: int = 0, limit: int = 50) -> List[TokenSettings]:
        """
        Récupérer toutes les configurations avec pagination.

        Args:
            skip: Nombre d'éléments à sauter
            limit: Nombre maximum d'éléments

        Returns:
            List[TokenSettings]: Liste des configurations
        """
        stmt = select(TokenSettings).order_by(
            desc(TokenSettings.is_active),
            desc(TokenSettings.created_at)
        ).offset(skip).limit(limit)
        result = await self.db.execute(stmt)
        return result.scalars().all()

    async def update(self, config_id: UUID, update_data: dict) -> Optional[TokenSettings]:
        """
        Mettre à jour une configuration.

        Args:
            config_id: ID de la configuration
            update_data: Données de mise à jour

        Returns:
            TokenSettings ou None: La configuration mise à jour
        """
        # Ajouter updated_at
        update_data["updated_at"] = update_data.get("updated_at", None)

        stmt = update(TokenSettings).where(
            TokenSettings.id == config_id
        ).values(**update_data).returning(TokenSettings)

        result = await self.db.execute(stmt)
        await self.db.commit()

        updated_config = result.scalar_one_or_none()
        return updated_config

    async def deactivate_all(self) -> None:
        """
        Désactiver toutes les configurations.
        """
        stmt = update(TokenSettings).where(
            TokenSettings.is_active == True
        ).values(is_active=False)
        await self.db.execute(stmt)
        await self.db.commit()

    async def activate(self, config_id: UUID) -> Optional[TokenSettings]:
        """
        Activer une configuration spécifique.

        Args:
            config_id: ID de la configuration à activer

        Returns:
            TokenSettings ou None: La configuration activée
        """
        # D'abord désactiver toutes les configurations
        await self.deactivate_all()

        # Puis activer la configuration spécifiée
        stmt = update(TokenSettings).where(
            TokenSettings.id == config_id
        ).values(is_active=True).returning(TokenSettings)

        result = await self.db.execute(stmt)
        await self.db.commit()

        return result.scalar_one_or_none()

    async def delete(self, config_id: UUID) -> bool:
        """
        Supprimer une configuration.

        Args:
            config_id: ID de la configuration à supprimer

        Returns:
            bool: True si supprimée, False sinon
        """
        config = await self.get_by_id(config_id)
        if not config:
            return False

        # Ne pas supprimer si c'est la configuration active
        if config.is_active:
            return False

        await self.db.delete(config)
        await self.db.commit()
        return True

    async def exists(self, config_id: UUID) -> bool:
        """
        Vérifier si une configuration existe.

        Args:
            config_id: ID de la configuration

        Returns:
            bool: True si elle existe
        """
        stmt = select(TokenSettings.id).where(TokenSettings.id == config_id)
        result = await self.db.execute(stmt)
        return result.scalar_one_or_none() is not None

    async def count(self) -> int:
        """
        Compter le nombre total de configurations.

        Returns:
            int: Nombre de configurations
        """
        from sqlalchemy import func
        stmt = select(func.count(TokenSettings.id))
        result = await self.db.execute(stmt)
        return result.scalar_one()

    async def get_latest_version(self) -> int:
        """
        Obtenir la dernière version de configuration.

        Returns:
            int: Dernière version
        """
        stmt = select(TokenSettings.version).order_by(
            desc(TokenSettings.version)
        ).limit(1)
        result = await self.db.execute(stmt)
        latest = result.scalar_one_or_none()
        return latest or 0