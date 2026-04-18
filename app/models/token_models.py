from sqlalchemy import Column, Integer, String, Boolean, DateTime, Text, func, Index
from sqlalchemy.dialects.postgresql import UUID
from datetime import datetime, timedelta
import uuid

from app.models.base import BaseModel
from app.database import Base


class TokenSettings(Base):
    """
    Configuration globale des paramètres de sécurité des tokens.
    Stockée en base de données avec chargement dynamique au démarrage.
    """
    __tablename__ = "token_settings"

    id = Column(Integer, primary_key=True, autoincrement=True)
    name = Column(String(100), unique=True, nullable=False)

    # Durée de vie des tokens (en minutes)
    access_token_lifetime  = Column(Integer, default=30,    nullable=False, comment="Durée de vie du token d'accès en minutes")
    refresh_token_lifetime = Column(Integer, default=10080, nullable=False, comment="Durée de vie du token de rafraîchissement en minutes (7 jours)")

    # Sécurité des sessions
    max_sessions_per_user = Column(Integer, default=5,  nullable=False, comment="Nombre maximum de sessions actives par utilisateur")
    session_ttl_hours     = Column(Integer, default=24, nullable=False, comment="Durée de vie des sessions en heures")

    # Gestion des tokens
    rotate_refresh_tokens = Column(Boolean, default=True,  nullable=False, comment="Générer un nouveau token de rafraîchissement à chaque utilisation")
    enable_blacklist      = Column(Boolean, default=True,  nullable=False, comment="Activer la liste noire des tokens")
    blacklist_ttl_minutes = Column(Integer, default=1440,  nullable=False, comment="Durée de conservation en liste noire (24h)")

    # Sécurité avancée
    require_https       = Column(Boolean, default=False, nullable=False, comment="Exiger HTTPS pour les tokens")
    validate_ip         = Column(Boolean, default=True,  nullable=False, comment="Valider l'IP de l'utilisateur")
    validate_user_agent = Column(Boolean, default=True,  nullable=False, comment="Valider le User-Agent")

    # Chiffrement
    encrypt_tokens = Column(Boolean, default=False, nullable=False, comment="Chiffrer les tokens en base")

    # Statut
    is_active  = Column(Boolean,  default=True,      nullable=False, comment="Configuration active")
    created_at = Column(DateTime, default=func.now(), nullable=False)
    updated_at = Column(DateTime, default=func.now(), onupdate=func.now(), nullable=False)

    __table_args__ = (
        Index('idx_token_settings_active', 'is_active'),
        Index('idx_token_settings_name',   'name'),
        {'comment': 'Configurations des paramètres de sécurité des tokens JWT'}
    )

    def __repr__(self):
        return f"<TokenSettings(name='{self.name}', active={self.is_active})>"

    def to_token_manager_config(self) -> dict:
        return {
            'access_token_lifetime_minutes' : self.access_token_lifetime,
            'refresh_token_lifetime_minutes': self.refresh_token_lifetime,
            'max_sessions_per_user'         : self.max_sessions_per_user,
            'session_ttl_hours'             : self.session_ttl_hours,
            'rotate_refresh_tokens'         : self.rotate_refresh_tokens,
            'enable_blacklist'              : self.enable_blacklist,
            'blacklist_ttl_minutes'         : self.blacklist_ttl_minutes,
            'require_https'                 : self.require_https,
            'validate_ip'                   : self.validate_ip,
            'validate_user_agent'           : self.validate_user_agent,
            'encrypt_tokens'                : self.encrypt_tokens,
        }

    @classmethod
    def get_default_config(cls) -> dict:
        return {
            'access_token_lifetime_minutes' : 30,
            'refresh_token_lifetime_minutes': 10080,
            'max_sessions_per_user'         : 5,
            'session_ttl_hours'             : 24,
            'rotate_refresh_tokens'         : True,
            'enable_blacklist'              : True,
            'blacklist_ttl_minutes'         : 1440,
            'require_https'                 : False,
            'validate_ip'                   : True,
            'validate_user_agent'           : True,
            'encrypt_tokens'                : False,
        }


class TokenManagerRecord(Base):
    """
    Enregistrement des tokens actifs avec tracking détaillé des devices.
    """
    __tablename__ = "token_manager"

    id = Column(Integer, primary_key=True, autoincrement=True)

    # Informations utilisateur
    user_id  = Column(Integer,     nullable=False, index=True)
    username = Column(String(255), nullable=False)

    # Tokens
    access_token_hash  = Column(String(128), nullable=False, index=True, comment="Hash du token d'accès")
    refresh_token_hash = Column(String(128), nullable=False, index=True, comment="Hash du token de rafraîchissement")

    # Timestamps
    created_at = Column(DateTime, default=func.now(),    nullable=False)
    expires_at = Column(DateTime, nullable=False,        index=True)
    last_used  = Column(DateTime, default=func.now(),    onupdate=func.now(), nullable=False)

    # État
    is_active     = Column(Boolean,  default=True,  nullable=False, index=True)
    is_revoked    = Column(Boolean,  default=False, nullable=False, index=True)
    revoked_at    = Column(DateTime, nullable=True)
    revoked_reason = Column(String(255), nullable=True)

    # Session
    session_id = Column(String(64), nullable=False, unique=True, index=True)
    ip_address = Column(String(45), nullable=True)
    user_agent = Column(Text,       nullable=True)

    # Device fingerprinting
    device_id     = Column(String(64),  nullable=False, index=True, comment="ID unique du device")
    device_family = Column(String(100), nullable=True)
    device_brand  = Column(String(100), nullable=True)
    device_model  = Column(String(100), nullable=True)
    device_type   = Column(String(20),  nullable=False, default='desktop')

    # Système d'exploitation
    os_family  = Column(String(100), nullable=True)
    os_version = Column(String(50),  nullable=True)

    # Navigateur
    browser_family  = Column(String(100), nullable=True)
    browser_version = Column(String(50),  nullable=True)

    # Localisation
    location = Column(String(255), nullable=True)

    # Métriques
    activity_count = Column(Integer, default=0, nullable=False)

    __table_args__ = (
        Index('idx_token_manager_user_active', 'user_id', 'is_active'),
        Index('idx_token_manager_expires',     'expires_at'),
        Index('idx_token_manager_revoked',     'is_revoked'),
        Index('idx_token_manager_device',      'device_id'),
        Index('idx_token_manager_session',     'session_id'),
        {'comment': 'Gestionnaire des tokens JWT avec tracking détaillé des devices'}
    )

    def __repr__(self):
        return f"<TokenManagerRecord(user_id={self.user_id}, session_id='{self.session_id}', active={self.is_active})>"

    def is_valid(self) -> bool:
        return (
            self.is_active and
            not self.is_revoked and
            self.expires_at > datetime.utcnow()
        )

    def get_device_info(self) -> dict:
        return {
            'device_id'      : self.device_id,
            'device_family'  : self.device_family,
            'device_brand'   : self.device_brand,
            'device_model'   : self.device_model,
            'device_type'    : self.device_type,
            'os_family'      : self.os_family,
            'os_version'     : self.os_version,
            'browser_family' : self.browser_family,
            'browser_version': self.browser_version,
            'location'       : self.location,
            'ip_address'     : self.ip_address,
            'last_used'      : self.last_used,
            'activity_count' : self.activity_count,
        }

    def update_activity(self):
        self.last_used = datetime.utcnow()
        self.activity_count += 1

    def revoke(self, reason: str = None):
        self.is_active    = False
        self.is_revoked   = True
        self.revoked_at   = datetime.utcnow()
        self.revoked_reason = reason