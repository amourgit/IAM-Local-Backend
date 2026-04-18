"""
Endpoints de gestion de la configuration des tokens.
API pour la gestion dynamique des paramètres de sécurité et de session.
"""

from typing import List, Optional
from uuid import UUID
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.dependencies import get_db, get_current_admin_user
from app.models.token_models import TokenSettings
from app.schemas.token_schemas import (
    TokenSettingsResponse,
    TokenSettingsCreate,
    TokenSettingsUpdate,
    ConfigurationManagementRequest,
    ConfigurationManagementResponse,
    ConfigurationHistoryResponse,
)
from app.services.token_manager.token_config_service import TokenConfigService
from app.repositories.token_config_repository import TokenConfigRepository

router = APIRouter(prefix="/token-config", tags=["Configuration des Tokens"])


@router.post(
    "/",
    response_model=TokenSettingsResponse,
    summary="Créer une nouvelle configuration",
    description="Créer une nouvelle configuration de tokens (admin seulement)"
)
async def create_token_config(
    config_data: TokenSettingsCreate,
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(get_current_admin_user)
) -> TokenSettingsResponse:
    """
    Créer une nouvelle configuration de tokens.

    - **config_data**: Données de la configuration à créer
    - **current_user**: Utilisateur admin authentifié (dépendances)
    """
    try:
        repository = TokenConfigRepository(db)
        config_service = TokenConfigService(repository)

        # Créer la nouvelle configuration
        config = await config_service.create_configuration(
            settings_data=config_data.dict(),
            created_by=current_user.get("user_id")
        )

        return TokenSettingsResponse.from_orm(config)

    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Erreur lors de la création de la configuration: {str(e)}"
        )


@router.get(
    "/active",
    response_model=TokenSettingsResponse,
    summary="Obtenir la configuration active",
    description="Récupérer la configuration de tokens actuellement active"
)
async def get_active_config(
    db: AsyncSession = Depends(get_db)
) -> TokenSettingsResponse:
    """
    Obtenir la configuration de tokens active.
    """
    try:
        repository = TokenConfigRepository(db)
        config_service = TokenConfigService(repository)

        config = await config_service.get_active_configuration()
        if not config:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Aucune configuration active trouvée"
            )

        return TokenSettingsResponse.from_orm(config)

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Erreur lors de la récupération de la configuration: {str(e)}"
        )


@router.get(
    "/",
    response_model=ConfigurationHistoryResponse,
    summary="Lister l'historique des configurations",
    description="Récupérer l'historique complet des configurations (admin seulement)"
)
async def list_configurations(
    skip: int = 0,
    limit: int = 50,
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(get_current_admin_user)
) -> ConfigurationHistoryResponse:
    """
    Lister toutes les configurations avec pagination.

    - **skip**: Nombre d'éléments à sauter
    - **limit**: Nombre maximum d'éléments à retourner
    """
    try:
        repository = TokenConfigRepository(db)
        config_service = TokenConfigService(repository)

        configs = await config_service.get_configuration_history(skip=skip, limit=limit)
        active_config = await config_service.get_active_configuration()

        return ConfigurationHistoryResponse(
            configurations=[TokenSettingsResponse.from_orm(c) for c in configs],
            total_count=len(configs),
            active_configuration=TokenSettingsResponse.from_orm(active_config) if active_config else None
        )

    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Erreur lors de la récupération des configurations: {str(e)}"
        )


@router.get(
    "/{config_id}",
    response_model=TokenSettingsResponse,
    summary="Obtenir une configuration par ID",
    description="Récupérer une configuration spécifique par son ID (admin seulement)"
)
async def get_config_by_id(
    config_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(get_current_admin_user)
) -> TokenSettingsResponse:
    """
    Obtenir une configuration par son ID.

    - **config_id**: ID de la configuration
    """
    try:
        repository = TokenConfigRepository(db)
        config_service = TokenConfigService(repository)

        config = await config_service.get_configuration_by_id(config_id)
        if not config:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Configuration non trouvée"
            )

        return TokenSettingsResponse.from_orm(config)

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Erreur lors de la récupération de la configuration: {str(e)}"
        )


@router.put(
    "/{config_id}",
    response_model=TokenSettingsResponse,
    summary="Mettre à jour une configuration",
    description="Mettre à jour une configuration existante (admin seulement)"
)
async def update_config(
    config_id: UUID,
    config_update: TokenSettingsUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(get_current_admin_user)
) -> TokenSettingsResponse:
    """
    Mettre à jour une configuration.

    - **config_id**: ID de la configuration à mettre à jour
    - **config_update**: Données de mise à jour
    """
    try:
        repository = TokenConfigRepository(db)
        config_service = TokenConfigService(repository)

        # Convertir les données de mise à jour en dict, en excluant les None
        update_data = config_update.dict(exclude_unset=True)

        config = await config_service.update_configuration(
            config_id=config_id,
            update_data=update_data,
            updated_by=current_user.get("user_id")
        )

        if not config:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Configuration non trouvée"
            )

        return TokenSettingsResponse.from_orm(config)

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Erreur lors de la mise à jour de la configuration: {str(e)}"
        )


@router.post(
    "/{config_id}/activate",
    response_model=ConfigurationManagementResponse,
    summary="Activer une configuration",
    description="Activer une configuration spécifique (admin seulement)"
)
async def activate_config(
    config_id: UUID,
    request: ConfigurationManagementRequest,
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(get_current_admin_user)
) -> ConfigurationManagementResponse:
    """
    Activer une configuration.

    - **config_id**: ID de la configuration à activer
    - **request**: Détails de l'activation
    """
    try:
        repository = TokenConfigRepository(db)
        config_service = TokenConfigService(repository)

        success, message, config, previous_id = await config_service.activate_configuration(
            config_id=config_id,
            activated_by=current_user.get("user_id"),
            version_comment=request.version_comment
        )

        return ConfigurationManagementResponse(
            success=success,
            message=message,
            configuration=TokenSettingsResponse.from_orm(config) if config else None,
            previous_version=previous_id
        )

    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Erreur lors de l'activation de la configuration: {str(e)}"
        )


@router.delete(
    "/{config_id}",
    response_model=ConfigurationManagementResponse,
    summary="Supprimer une configuration",
    description="Supprimer une configuration (admin seulement, ne peut pas supprimer la configuration active)"
)
async def delete_config(
    config_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(get_current_admin_user)
) -> ConfigurationManagementResponse:
    """
    Supprimer une configuration.

    - **config_id**: ID de la configuration à supprimer
    """
    try:
        repository = TokenConfigRepository(db)
        config_service = TokenConfigService(repository)

        success, message = await config_service.delete_configuration(
            config_id=config_id,
            deleted_by=current_user.get("user_id")
        )

        return ConfigurationManagementResponse(
            success=success,
            message=message
        )

    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Erreur lors de la suppression de la configuration: {str(e)}"
        )


@router.post(
    "/refresh-cache",
    summary="Rafraîchir le cache de configuration",
    description="Forcer le rafraîchissement du cache de configuration (admin seulement)"
)
async def refresh_config_cache(
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(get_current_admin_user)
):
    """
    Rafraîchir le cache de configuration.
    """
    try:
        repository = TokenConfigRepository(db)
        config_service = TokenConfigService(repository)

        await config_service.refresh_configuration_cache()

        return {"message": "Cache de configuration rafraîchi avec succès"}

    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Erreur lors du rafraîchissement du cache: {str(e)}"
        )