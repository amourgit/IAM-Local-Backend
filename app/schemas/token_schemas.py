"""
Schémas Pydantic pour les tokens JWT.
Définition des structures de données pour l'authentification.
"""

from datetime import datetime
from typing import Optional, List, Dict, Any
from uuid import UUID

from pydantic import BaseModel, Field, field_validator


# ── Schémas de Base ───────────────────────────────────────────────

class TokenBase(BaseModel):
    """Schéma de base pour tous les tokens."""
    iss: str = Field(..., description="Issuer du token")
    sub: str = Field(..., description="Subject (ID utilisateur)")
    iat: int = Field(..., description="Issued at (timestamp)")
    exp: int = Field(..., description="Expiration (timestamp)")
    jti: Optional[str] = Field(None, description="JWT ID")

    @field_validator('exp')
    @classmethod
    def exp_must_be_future(cls, v):
        if v < datetime.utcnow().timestamp():
            raise ValueError('Token expiré')
        return v


# ── Schémas d'Access Token ────────────────────────────────────────

class AccessTokenPayload(TokenBase):
    """Payload d'un access token."""
    session_id: str = Field(..., description="ID de session")
    type_profil: Optional[str] = Field(None, description="Type de profil utilisateur")
    permissions: List[str] = Field(default_factory=list, description="Permissions de l'utilisateur")
    roles: List[str] = Field(default_factory=list, description="Rôles de l'utilisateur")
    is_admin: bool = Field(False, description="Flag administrateur")
    token_type: str = Field("access", description="Type de token")
    version: str = Field("1.0", description="Version du schéma")


class AccessTokenResponse(BaseModel):
    """Réponse lors de l'émission d'un access token."""
    access_token: str = Field(..., description="Token d'accès JWT")
    token_type: str = Field("bearer", description="Type de token")
    expires_in: int = Field(..., description="Durée de validité en secondes")


# ── Schémas de Refresh Token ──────────────────────────────────────

class RefreshTokenPayload(TokenBase):
    """Payload d'un refresh token."""
    session_id: str = Field(..., description="ID de session")
    token_id: str = Field(..., description="ID unique du token")
    token_type: str = Field("refresh", description="Type de token")
    version: str = Field("1.0", description="Version du schéma")


class RefreshTokenResponse(BaseModel):
    """Réponse lors de l'émission d'un refresh token."""
    refresh_token: str = Field(..., description="Refresh token JWT")


# ── Schémas de Session ────────────────────────────────────────────

class SessionInfo(BaseModel):
    """Informations sur une session utilisateur."""
    id: str = Field(..., description="ID de la session")
    user_id: str = Field(..., description="ID de l'utilisateur")
    status: str = Field(..., description="Statut de la session")
    created_at: str = Field(..., description="Date de création")
    last_activity: str = Field(..., description="Dernière activité")
    expires_at: str = Field(..., description="Date d'expiration")
    user_agent: Optional[str] = Field(None, description="User-Agent")
    ip_address: Optional[str] = Field(None, description="Adresse IP")
    metadata: Dict[str, Any] = Field(default_factory=dict, description="Métadonnées")
    activity_count: int = Field(0, description="Nombre d'activités")


class SessionCreateRequest(BaseModel):
    """Requête de création de session."""
    user_agent: Optional[str] = None
    ip_address: Optional[str] = None
    metadata: Optional[Dict[str, Any]] = None


# ── Schémas d'Authentification ────────────────────────────────────

class LoginRequest(BaseModel):
    """Requête de connexion."""
    username: str = Field(..., min_length=1, description="Nom d'utilisateur")
    password: str = Field(..., min_length=1, description="Mot de passe")


class LoginResponse(BaseModel):
    """Réponse de connexion."""
    access_token: str = Field(..., description="Token d'accès")
    refresh_token: str = Field(..., description="Refresh token")
    token_type: str = Field("bearer", description="Type de token")
    expires_in: int = Field(..., description="Durée de validité en secondes")
    user: Dict[str, Any] = Field(..., description="Informations utilisateur")
    session_id: str = Field(..., description="ID de session")


class RefreshTokenRequest(BaseModel):
    """Requête de rafraîchissement de token."""
    refresh_token: str = Field(..., description="Refresh token")


class RefreshTokenResponse(BaseModel):
    """Réponse de rafraîchissement de token."""
    access_token: str = Field(..., description="Nouveau token d'accès")
    token_type: str = Field("bearer", description="Type de token")
    expires_in: int = Field(..., description="Durée de validité en secondes")


# ── Schémas de Validation ─────────────────────────────────────────

class TokenValidationRequest(BaseModel):
    """Requête de validation de token."""
    token: str = Field(..., description="Token à valider")
    token_type: Optional[str] = Field("auto", description="Type de token")


class TokenValidationResponse(BaseModel):
    """Réponse de validation de token."""
    valid: bool = Field(..., description="Token valide")
    token_type: Optional[str] = Field(None, description="Type de token détecté")
    user_id: Optional[str] = Field(None, description="ID utilisateur")
    session_id: Optional[str] = Field(None, description="ID de session")
    permissions: Optional[List[str]] = Field(None, description="Permissions")
    roles: Optional[List[str]] = Field(None, description="Rôles")
    type_profil: Optional[str] = Field(None, description="Type de profil")
    is_admin: Optional[bool] = Field(None, description="Flag admin")
    issued_at: Optional[str] = Field(None, description="Date d'émission")
    expires_at: Optional[str] = Field(None, description="Date d'expiration")
    error: Optional[str] = Field(None, description="Message d'erreur")


class EndpointAuthorizationCheck(BaseModel):
    """Vérification d'autorisation pour un endpoint."""
    authorized: bool = Field(..., description="Accès autorisé")
    user_id: Optional[str] = Field(None, description="ID utilisateur")
    session_id: Optional[str] = Field(None, description="ID de session")
    permissions: Dict[str, Any] = Field(default_factory=dict, description="Vérification permissions")
    roles: Dict[str, Any] = Field(default_factory=dict, description="Vérification rôles")
    admin: Dict[str, Any] = Field(default_factory=dict, description="Vérification admin")
    error: Optional[str] = Field(None, description="Message d'erreur")
    error_type: Optional[str] = Field(None, description="Type d'erreur")


# ── Schémas de Blacklist ──────────────────────────────────────────

class BlacklistEntry(BaseModel):
    """Entrée de blacklist."""
    identifier: str = Field(..., description="Identifiant blacklisté")
    reason: str = Field(..., description="Raison de la blacklist")
    blacklisted_at: str = Field(..., description="Date de blacklist")
    ttl_minutes: int = Field(..., description="Durée de vie en minutes")
    expires_at: str = Field(..., description="Date d'expiration")


class BlacklistInfo(BaseModel):
    """Informations sur une entrée blacklist."""
    session_id: Optional[str] = None
    user_id: Optional[str] = None
    token_jti: Optional[str] = None
    reason: str
    blacklisted_at: str
    ttl_minutes: int
    expires_at: str
    type: Optional[str] = None


# ── Schémas de Synchronisation ────────────────────────────────────

class IAMCentralUserData(BaseModel):
    """Données utilisateur depuis IAM Central."""
    user_id_national: str = Field(..., description="ID national")
    nom: str = Field(..., description="Nom")
    prenom: str = Field(..., description="Prénom")
    email: str = Field(..., description="Email")
    type_profil: str = Field(..., description="Type de profil")
    date_naissance: Optional[str] = Field(None, description="Date de naissance")
    telephone: Optional[str] = Field(None, description="Téléphone")
    statut: str = Field("active", description="Statut du compte")
    etablissement_id: Optional[str] = Field(None, description="ID établissement")
    synchronise_le: str = Field(default_factory=lambda: datetime.utcnow().isoformat())


class IAMCentralStatusCheck(BaseModel):
    """Vérification de statut auprès d'IAM Central."""
    status: str = Field(..., description="Statut du compte")
    reason: Optional[str] = Field(None, description="Raison du statut")
    last_check: str = Field(..., description="Dernière vérification")


class SyncBatchRequest(BaseModel):
    """Requête de synchronisation en batch."""
    user_ids: List[str] = Field(..., description="IDs des utilisateurs à synchroniser")


class SyncBatchResponse(BaseModel):
    """Réponse de synchronisation en batch."""
    users: Dict[str, IAMCentralUserData] = Field(default_factory=dict, description="Utilisateurs trouvés")
    not_found: List[str] = Field(default_factory=list, description="Utilisateurs non trouvés")
    error: Optional[str] = Field(None, description="Message d'erreur")


# ── Schémas Métriques ─────────────────────────────────────────────

class TokenMetrics(BaseModel):
    """Métriques des tokens."""
    active_sessions: int = Field(0, description="Sessions actives")
    blacklisted_sessions: int = Field(0, description="Sessions blacklistées")
    tokens_issued_today: int = Field(0, description="Tokens émis aujourd'hui")
    sync_status: Dict[str, Any] = Field(default_factory=dict, description="Statut synchronisation")


class SessionStats(BaseModel):
    """Statistiques des sessions."""
    total_keys: int = Field(0, description="Total des clés en cache")
    active: int = Field(0, description="Sessions actives")
    revoked: int = Field(0, description="Sessions révoquées")
    by_user_agent: Dict[str, int] = Field(default_factory=dict, description="Répartition par User-Agent")
    by_ip: Dict[str, int] = Field(default_factory=dict, description="Répartition par IP")
    oldest_session: Optional[Dict[str, Any]] = Field(None, description="Plus ancienne session")
    newest_session: Optional[Dict[str, Any]] = Field(None, description="Plus récente session")
    timestamp: str = Field(..., description="Horodatage des stats")


# ── Schémas d'Erreur ──────────────────────────────────────────────

class TokenErrorDetail(BaseModel):
    """Détail d'erreur de token."""
    type: str = Field(..., description="Type d'erreur")
    message: str = Field(..., description="Message d'erreur")
    details: Optional[Dict[str, Any]] = Field(None, description="Détails supplémentaires")


class TokenValidationError(BaseModel):
    """Erreur de validation de token."""
    token_type: Optional[str] = Field(None, description="Type de token")
    error: TokenErrorDetail = Field(..., description="Détail de l'erreur")
    timestamp: str = Field(default_factory=lambda: datetime.utcnow().isoformat())


# ── Schémas d'Analyse d'Appareil ──────────────────────────────────

class DeviceInfo(BaseModel):
    """Informations détaillées sur l'appareil utilisateur."""
    device_brand: Optional[str] = Field(None, description="Marque de l'appareil")
    device_model: Optional[str] = Field(None, description="Modèle de l'appareil")
    device_family: Optional[str] = Field(None, description="Famille d'appareil")
    os_family: Optional[str] = Field(None, description="Famille du système d'exploitation")
    os_version: Optional[str] = Field(None, description="Version du système d'exploitation")
    browser_family: Optional[str] = Field(None, description="Famille du navigateur")
    browser_version: Optional[str] = Field(None, description="Version du navigateur")
    is_mobile: bool = Field(False, description="Appareil mobile")
    is_tablet: bool = Field(False, description="Tablette")
    is_pc: bool = Field(False, description="Ordinateur")
    is_bot: bool = Field(False, description="Robot/bot")
    is_touch_capable: bool = Field(False, description="Capable de toucher")
    user_agent_string: Optional[str] = Field(None, description="Chaîne User-Agent complète")


# ── Schémas de Configuration Dynamique ────────────────────────────

class TokenSettingsBase(BaseModel):
    """Configuration de base pour les tokens."""
    access_token_lifetime_minutes: int = Field(15, description="Durée de vie access token (minutes)")
    refresh_token_lifetime_days: int = Field(30, description="Durée de vie refresh token (jours)")
    max_sessions_per_user: int = Field(5, description="Nombre maximum de sessions par utilisateur")
    session_timeout_minutes: int = Field(480, description="Timeout de session (minutes)")
    enable_ip_validation: bool = Field(True, description="Activer validation IP")
    enable_user_agent_validation: bool = Field(True, description="Activer validation User-Agent")
    enable_device_tracking: bool = Field(True, description="Activer suivi détaillé des appareils")
    blacklist_ttl_minutes: int = Field(1440, description="TTL blacklist (minutes)")
    jwt_algorithm: str = Field("RS256", description="Algorithme JWT")
    jwt_issuer: str = Field("iam-local", description="Émetteur JWT")
    enable_token_rotation: bool = Field(True, description="Activer rotation des tokens")
    max_failed_attempts: int = Field(5, description="Nombre maximum de tentatives échouées")
    lockout_duration_minutes: int = Field(15, description="Durée de verrouillage après échec (minutes)")
    enable_rate_limiting: bool = Field(True, description="Activer limitation du taux")
    rate_limit_requests: int = Field(100, description="Nombre de requêtes autorisées")
    rate_limit_window_minutes: int = Field(15, description="Fenêtre de limitation (minutes)")


class TokenSettingsCreate(TokenSettingsBase):
    """Création de configuration token."""
    pass


class TokenSettingsUpdate(BaseModel):
    """Mise à jour de configuration token."""
    access_token_lifetime_minutes: Optional[int] = None
    refresh_token_lifetime_days: Optional[int] = None
    max_sessions_per_user: Optional[int] = None
    session_timeout_minutes: Optional[int] = None
    enable_ip_validation: Optional[bool] = None
    enable_user_agent_validation: Optional[bool] = None
    enable_device_tracking: Optional[bool] = None
    blacklist_ttl_minutes: Optional[int] = None
    jwt_algorithm: Optional[str] = None
    jwt_issuer: Optional[str] = None
    enable_token_rotation: Optional[bool] = None
    max_failed_attempts: Optional[int] = None
    lockout_duration_minutes: Optional[int] = None
    enable_rate_limiting: Optional[bool] = None
    rate_limit_requests: Optional[int] = None
    rate_limit_window_minutes: Optional[int] = None


class TokenSettingsResponse(TokenSettingsBase):
    """Réponse de configuration token."""
    id: UUID = Field(..., description="ID de la configuration")
    created_at: datetime = Field(..., description="Date de création")
    updated_at: datetime = Field(..., description="Date de mise à jour")
    is_active: bool = Field(True, description="Configuration active")
    version: int = Field(1, description="Version de la configuration")


# ── Schémas de Gestion de Configuration ───────────────────────────

class ConfigurationManagementRequest(BaseModel):
    """Requête de gestion de configuration."""
    action: str = Field(..., description="Action à effectuer", pattern="^(create|update|activate|deactivate|delete)$")
    settings: Optional[TokenSettingsUpdate] = Field(None, description="Paramètres à modifier")
    version_comment: Optional[str] = Field(None, description="Commentaire de version")


class ConfigurationManagementResponse(BaseModel):
    """Réponse de gestion de configuration."""
    success: bool = Field(..., description="Opération réussie")
    message: str = Field(..., description="Message de réponse")
    configuration: Optional[TokenSettingsResponse] = Field(None, description="Configuration actuelle")
    previous_version: Optional[UUID] = Field(None, description="Version précédente")
    error: Optional[str] = Field(None, description="Message d'erreur")


class ConfigurationHistoryResponse(BaseModel):
    """Historique des configurations."""
    configurations: List[TokenSettingsResponse] = Field(default_factory=list, description="Liste des configurations")
    total_count: int = Field(0, description="Nombre total")
    active_configuration: Optional[TokenSettingsResponse] = Field(None, description="Configuration active")


# ── Schémas Étendus pour Authentification ─────────────────────────

class LoginRequestExtended(LoginRequest):
    """Requête de connexion étendue avec suivi d'appareil."""
    user_agent: Optional[str] = Field(None, description="User-Agent du client")
    ip_address: Optional[str] = Field(None, description="Adresse IP du client")
    device_info: Optional[DeviceInfo] = Field(None, description="Informations détaillées sur l'appareil")


class LoginResponseExtended(LoginResponse):
    """Réponse de connexion étendue avec informations d'appareil."""
    device_info: Optional[DeviceInfo] = Field(None, description="Informations sur l'appareil utilisé")
    session_limits: Dict[str, Any] = Field(default_factory=dict, description="Limites de session appliquées")


class SessionInfoExtended(SessionInfo):
    """Informations de session étendues avec suivi d'appareil."""
    device_info: Optional[DeviceInfo] = Field(None, description="Informations détaillées sur l'appareil")
    configuration_version: Optional[int] = Field(None, description="Version de configuration utilisée")
    security_validations: Dict[str, bool] = Field(default_factory=dict, description="Validations de sécurité appliquées")


class TokenValidationResponseExtended(TokenValidationResponse):
    """Réponse de validation étendue avec informations d'appareil."""
    device_info: Optional[DeviceInfo] = Field(None, description="Informations sur l'appareil")
    configuration_applied: Optional[Dict[str, Any]] = Field(None, description="Configuration appliquée")
    security_checks: Dict[str, bool] = Field(default_factory=dict, description="Contrôles de sécurité effectués")


# ── Schémas de Gestion des Credentials ─────────────────────────────

class ChangePasswordRequest(BaseModel):
    """Requête de changement de mot de passe."""
    old_password: str = Field(..., description="Ancien mot de passe", min_length=1)
    new_password: str = Field(..., description="Nouveau mot de passe", min_length=8)
    confirm_password: str = Field(..., description="Confirmation du nouveau mot de passe", min_length=8)

    @field_validator('new_password')
    @classmethod
    def validate_password_strength(cls, v):
        """Validation basique de la force du mot de passe."""
        if len(v) < 8:
            raise ValueError('Le mot de passe doit contenir au moins 8 caractères')
        if not any(c.isupper() for c in v):
            raise ValueError('Le mot de passe doit contenir au moins une majuscule')
        if not any(c.islower() for c in v):
            raise ValueError('Le mot de passe doit contenir au moins une minuscule')
        if not any(c.isdigit() for c in v):
            raise ValueError('Le mot de passe doit contenir au moins un chiffre')
        return v

    @field_validator('confirm_password')
    @classmethod
    def passwords_match(cls, v, info):
        if 'new_password' in info.data and v != info.data['new_password']:
            raise ValueError('Les mots de passe ne correspondent pas')
        return v


class ChangePasswordResponse(BaseModel):
    """Réponse de changement de mot de passe."""
    success: bool = Field(..., description="Succès de l'opération")
    message: str = Field(..., description="Message informatif")
    password_changed_at: Optional[datetime] = Field(None, description="Date du changement")


class ResetPasswordRequest(BaseModel):
    """Requête de réinitialisation de mot de passe (admin seulement)."""
    profil_id: UUID = Field(..., description="ID du profil à réinitialiser")
    temp_password: Optional[str] = Field(None, description="Mot de passe temporaire (généré si non fourni)")


class ResetPasswordResponse(BaseModel):
    """Réponse de réinitialisation de mot de passe."""
    success: bool = Field(..., description="Succès de l'opération")
    temp_password: str = Field(..., description="Mot de passe temporaire généré")
    message: str = Field(..., description="Message informatif")