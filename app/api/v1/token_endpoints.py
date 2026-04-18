"""
Endpoints API pour la gestion des tokens JWT.
Points d'entrée pour l'authentification et la gestion des sessions.
"""

from fastapi import APIRouter, Depends, HTTPException, status, Request
from sqlalchemy.ext.asyncio import AsyncSession
from typing import Dict, Any, Optional

from app.database import get_db
from app.middleware.auth import get_current_user, CurrentUser
from app.services.token_manager import TokenManager
from app.schemas.token_schemas import (
    LoginRequest,
    LoginResponse,
    RefreshTokenRequest,
    RefreshTokenResponse,
    TokenValidationRequest,
    TokenValidationResponse,
    EndpointAuthorizationCheck,
    TokenMetrics,
    SessionStats,
    ChangePasswordRequest,
    ChangePasswordResponse,
    ResetPasswordRequest,
    ResetPasswordResponse,
)
from app.core.exceptions import AuthenticationError, TokenError

router = APIRouter(prefix="/tokens", tags=["IAM — Tokens"])


# ── Authentification ──────────────────────────────────────────────

@router.post("/login", response_model=LoginResponse)
async def login(
    request: LoginRequest,
    db: AsyncSession = Depends(get_db),
    req: Request = None
) -> LoginResponse:
    """
    Authentification d'un utilisateur avec credentials locaux.

    Génère un access token et un refresh token pour la session.
    """
    try:
        token_manager = TokenManager()

        # Récupération des informations de contexte
        user_agent = req.headers.get("user-agent") if req else None
        ip_address = req.client.host if req and req.client else None

        # Authentification
        result = await token_manager.authenticate_user(
            username=request.username,
            password=request.password,
            user_agent=user_agent,
            ip_address=ip_address
        )

        return LoginResponse(**result)

    except AuthenticationError as e:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=str(e)
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Erreur d'authentification: {str(e)}"
        )


@router.post("/refresh", response_model=RefreshTokenResponse)
async def refresh_token(
    request: RefreshTokenRequest,
    db: AsyncSession = Depends(get_db)
) -> RefreshTokenResponse:
    """
    Rafraîchit un access token en utilisant un refresh token valide.
    """
    try:
        token_manager = TokenManager()

        result = await token_manager.refresh_access_token(request.refresh_token, db)

        return RefreshTokenResponse(**result)

    except TokenError as e:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=str(e)
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Erreur de rafraîchissement: {str(e)}"
        )


# ── Validation et Inspection ──────────────────────────────────────

@router.post("/validate", response_model=TokenValidationResponse)
async def validate_token(
    request: TokenValidationRequest,
    current_user: CurrentUser = Depends(get_current_user)
) -> TokenValidationResponse:
    """
    Valide un token et retourne ses informations détaillées.
    Nécessite d'être authentifié.
    """
    try:
        token_manager = TokenManager()
        validator = token_manager.validator

        # Validation du token
        token_type, payload = await validator.validate_token(
            request.token,
            request.token_type
        )

        # Construction de la réponse
        response_data = {
            "valid": True,
            "token_type": token_type,
            "user_id": payload.get("sub"),
            "session_id": payload.get("session_id"),
            "permissions": payload.get("permissions", []),
            "roles": payload.get("roles", []),
            "type_profil": payload.get("type_profil"),
            "is_admin": payload.get("is_admin", False),
            "issued_at": payload.get("iat"),
            "expires_at": payload.get("exp")
        }

        # Conversion timestamps
        if response_data["issued_at"]:
            from datetime import datetime
            response_data["issued_at"] = datetime.utcfromtimestamp(
                response_data["issued_at"]
            ).isoformat()

        if response_data["expires_at"]:
            from datetime import datetime
            response_data["expires_at"] = datetime.utcfromtimestamp(
                response_data["expires_at"]
            ).isoformat()

        return TokenValidationResponse(**response_data)

    except TokenError as e:
        return TokenValidationResponse(
            valid=False,
            error=str(e)
        )
    except Exception as e:
        return TokenValidationResponse(
            valid=False,
            error=f"Erreur de validation: {str(e)}"
        )


@router.post("/check-authorization", response_model=EndpointAuthorizationCheck)
async def check_endpoint_authorization(
    path: str,
    method: str = "GET",
    current_user: CurrentUser = Depends(get_current_user)
) -> EndpointAuthorizationCheck:
    """
    Vérifie si l'utilisateur actuel est autorisé à accéder à un endpoint.
    """
    try:
        token_manager = TokenManager()
        validator = token_manager.validator

        # Simulation de validation d'endpoint
        # En production, ceci serait fait automatiquement par le middleware
        auth_check = validator.validate_for_endpoint(
            token="",  # Le middleware fournit le token
            required_permissions=[],  # À déterminer depuis la config endpoint
            required_roles=[],
            allow_admin=True
        )

        # Pour l'instant, réponse basique
        return EndpointAuthorizationCheck(
            authorized=True,
            user_id=str(current_user.profil_id),
            session_id=str(current_user.session_id)
        )

    except Exception as e:
        return EndpointAuthorizationCheck(
            authorized=False,
            error=str(e),
            error_type="validation_error"
        )


# ── Gestion des Sessions ──────────────────────────────────────────

@router.post("/logout")
async def logout(
    current_user: CurrentUser = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
) -> Dict[str, str]:
    """
    Déconnexion de l'utilisateur actuel.
    Révoque la session en cours.
    """
    try:
        token_manager = TokenManager()

        await token_manager.revoke_session(
            session_id=current_user.session_id,
            reason="user_logout"
        )

        return {"message": "Déconnexion réussie"}

    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Erreur de déconnexion: {str(e)}"
        )


@router.get("/sessions")
async def get_my_sessions(
    current_user: CurrentUser = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
) -> Dict[str, Any]:
    """
    Récupère les sessions actives de l'utilisateur actuel.
    """
    try:
        token_manager = TokenManager()
        sessions = await token_manager.sessions.get_user_sessions(current_user.profil_id)

        return {
            "sessions": sessions,
            "count": len(sessions)
        }

    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Erreur récupération sessions: {str(e)}"
        )


@router.delete("/sessions/{session_id}")
async def revoke_session(
    session_id: str,
    current_user: CurrentUser = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
) -> Dict[str, str]:
    """
    Révoque une session spécifique de l'utilisateur.
    """
    try:
        from uuid import UUID
        session_uuid = UUID(session_id)

        token_manager = TokenManager()

        # Vérification que la session appartient à l'utilisateur
        session = await token_manager.sessions.get_session(session_uuid)
        if not session or session["user_id"] != str(current_user.profil_id):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Session non trouvée ou accès non autorisé"
            )

        await token_manager.revoke_session(
            session_id=session_uuid,
            reason="user_revoked"
        )

        return {"message": "Session révoquée"}

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Erreur révocation session: {str(e)}"
        )


# ── Métriques et Monitoring (Admin seulement) ─────────────────────

@router.get("/metrics", response_model=TokenMetrics)
async def get_token_metrics(
    current_user: CurrentUser = Depends(get_current_user)
) -> TokenMetrics:
    """
    Métriques du système de tokens.
    Réservé aux administrateurs.
    """
    if not current_user.is_admin:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Accès réservé aux administrateurs"
        )

    try:
        token_manager = TokenManager()
        metrics = await token_manager.get_metrics()

        return TokenMetrics(**metrics)

    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Erreur récupération métriques: {str(e)}"
        )


@router.get("/sessions/stats", response_model=SessionStats)
async def get_session_stats(
    current_user: CurrentUser = Depends(get_current_user)
) -> SessionStats:
    """
    Statistiques détaillées des sessions.
    Réservé aux administrateurs.
    """
    if not current_user.is_admin:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Accès réservé aux administrateurs"
        )

    try:
        token_manager = TokenManager()
        stats = await token_manager.sessions.get_session_stats()

        return SessionStats(**stats)

    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Erreur récupération statistiques: {str(e)}"
        )


# ── Synchronisation IAM Central ───────────────────────────────────

@router.post("/sync/{user_id_national}")
async def sync_user_from_iam_central(
    user_id_national: str,
    current_user: CurrentUser = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
) -> Dict[str, Any]:
    """
    Synchronise un utilisateur depuis IAM Central.
    Utilisé lors de l'enregistrement dans les modules métier.
    """
    try:
        token_manager = TokenManager()

        user_data = await token_manager.sync_user_from_iam_central(user_id_national)

        if user_data:
            return {
                "synced": True,
                "user_data": user_data,
                "message": f"Utilisateur {user_id_national} synchronisé"
            }
        else:
            return {
                "synced": False,
                "message": f"Utilisateur {user_id_national} non trouvé dans IAM Central"
            }

    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Erreur synchronisation: {str(e)}"
        )


@router.get("/sync/status")
async def get_sync_status(
    current_user: CurrentUser = Depends(get_current_user)
) -> Dict[str, Any]:
    """
    État de la synchronisation avec IAM Central.
    """
    try:
        token_manager = TokenManager()
        status = await token_manager.sync.get_sync_status()

        return status

    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Erreur vérification statut sync: {str(e)}"
        )


# ── Gestion des Credentials ───────────────────────────────────────

@router.post("/change-password", response_model=ChangePasswordResponse)
async def change_password(
    request: ChangePasswordRequest,
    current_user: CurrentUser = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
) -> ChangePasswordResponse:
    """
    Changement de mot de passe pour l'utilisateur connecté.

    Nécessite l'ancien mot de passe pour validation.
    """
    try:
        from app.services.credential_service import CredentialService

        credential_service = CredentialService(db)

        # Changer le mot de passe
        success = await credential_service.change_password(
            profil_id=current_user.id,
            old_password=request.old_password,
            new_password=request.new_password
        )

        if not success:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Échec du changement de mot de passe"
            )

        # Récupérer la date du changement
        from app.repositories.profil_local import ProfilLocalRepository
        repo = ProfilLocalRepository(db)
        profil = await repo.get_by_id(current_user.id)

        return ChangePasswordResponse(
            success=True,
            message="Mot de passe changé avec succès",
            password_changed_at=profil.password_changed_at if profil else None
        )

    except AuthenticationError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Erreur changement mot de passe: {str(e)}"
        )


@router.post("/admin/reset-password", response_model=ResetPasswordResponse)
async def admin_reset_password(
    request: ResetPasswordRequest,
    current_user: CurrentUser = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
) -> ResetPasswordResponse:
    """
    Réinitialisation de mot de passe par un administrateur.

    Génère un mot de passe temporaire pour le profil spécifié.
    Nécessite les permissions d'administration.
    """
    try:
        # Vérifier les permissions admin
        if "iam.admin" not in current_user.roles:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Permissions insuffisantes"
            )

        from app.services.credential_service import CredentialService

        credential_service = CredentialService(db)

        # Réinitialiser le mot de passe
        temp_password = await credential_service.reset_password(
            profil_id=request.profil_id,
            temp_password=request.temp_password
        )

        return ResetPasswordResponse(
            success=True,
            temp_password=temp_password,
            message=f"Mot de passe réinitialisé pour le profil {request.profil_id}"
        )

    except AuthenticationError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Erreur réinitialisation mot de passe: {str(e)}"
        )