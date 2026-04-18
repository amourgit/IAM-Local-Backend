"""
Dépendances communes pour les endpoints FastAPI.
"""

from typing import Optional
from uuid import UUID
from fastapi import Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.core.exceptions import UnauthorizedError, ForbiddenError


async def get_current_user(
    db: AsyncSession = Depends(get_db),
) -> dict:
    """
    Récupère l'utilisateur courant depuis le contexte de la requête.
    À implémenter avec extraction depuis JWT/token.
    """
    # Placeholder - à implémenter selon la stratégie d'authentification
    raise UnauthorizedError("Authentification requise")


async def get_current_admin_user(
    current_user: dict = Depends(get_current_user),
) -> dict:
    """
    Vérifie que l'utilisateur courant a les droits administrateur.
    """
    # Vérifier si l'utilisateur a le rôle admin
    if not current_user.get("is_admin", False):
        raise ForbiddenError("Accès réservé aux administrateurs")
    
    return current_user
