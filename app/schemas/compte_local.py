from typing import Optional, Any
from uuid import UUID
from datetime import datetime
from pydantic import Field, EmailStr
from app.schemas.base import BaseSchema, BaseResponseSchema
from app.core.enums import StatutProfil


# ─────────────────────────────────────────────────────────────
#  CREATE
# ─────────────────────────────────────────────────────────────

class CompteLocalCreateSchema(BaseSchema):
    """
    Création manuelle d'un compte local.
    Utilisé pour les comptes sans SSO IAM Central
    (ex : bootstrap, personnel externe, etc.)
    """
    user_id_national     : Optional[UUID] = None
    nom                  : Optional[str]  = None
    prenom               : Optional[str]  = None
    email                : Optional[str]  = None
    telephone            : Optional[str]  = None
    identifiant_national : Optional[str]  = None
    meta_data            : Optional[Any]  = {}
    notes                : Optional[str]  = None


class CompteLocalAvecCredentialsCreateSchema(BaseSchema):
    """
    Création d'un compte local avec credentials pour
    authentification locale (hors SSO IAM Central).
    Utilisé pour le bootstrap et les utilisateurs sans accès SSO.
    """
    nom                     : str
    prenom                  : str
    email                   : str
    telephone               : Optional[str] = None
    identifiant_national    : str
    username                : str
    password                : str
    require_password_change : bool         = True
    meta_data               : Optional[Any] = {}
    notes                   : Optional[str] = None


class CompteSyncSchema(BaseSchema):
    """
    Payload de synchronisation depuis IAM Central.
    Envoyé à chaque connexion SSO pour mettre à jour
    les données dénormalisées du compte local.
    """
    user_id_national     : UUID
    nom                  : str
    prenom               : str
    email                : str
    telephone            : Optional[str] = None
    identifiant_national : Optional[str] = None
    type_profil          : Optional[str] = None   # type suggéré par IAM Central
    snapshot_iam_central : Optional[Any] = None


# ─────────────────────────────────────────────────────────────
#  UPDATE
# ─────────────────────────────────────────────────────────────

class CompteLocalUpdateSchema(BaseSchema):
    """Mise à jour manuelle par un administrateur."""
    nom                  : Optional[str] = None
    prenom               : Optional[str] = None
    email                : Optional[str] = None
    telephone            : Optional[str] = None
    identifiant_national : Optional[str] = None
    preferences          : Optional[Any] = None
    meta_data            : Optional[Any] = None
    notes                : Optional[str] = None


class SuspendreCompteSchema(BaseSchema):
    raison : str = Field(..., min_length=5)


# ─────────────────────────────────────────────────────────────
#  RESPONSE
# ─────────────────────────────────────────────────────────────

class CompteLocalResponseSchema(BaseResponseSchema):
    """Réponse complète d'un compte local."""
    user_id_national        : Optional[UUID]     = None
    nom                     : Optional[str]      = None
    prenom                  : Optional[str]      = None
    email                   : Optional[str]      = None
    telephone               : Optional[str]      = None
    identifiant_national    : Optional[str]      = None
    username                : Optional[str]      = None
    statut                  : str
    raison_suspension       : Optional[str]      = None
    derniere_connexion      : Optional[datetime] = None
    nb_connexions           : Optional[str]      = None
    premiere_connexion      : Optional[datetime] = None
    require_password_change : bool               = False
    preferences             : Optional[Any]      = {}
    meta_data               : Optional[Any]      = {}
    notes                   : Optional[str]      = None

    # Informations calculées
    has_credentials         : Optional[bool]     = None
    nb_profils              : Optional[int]      = None


class CompteLocalListSchema(BaseResponseSchema):
    """Réponse allégée pour les listes."""
    user_id_national     : Optional[UUID]     = None
    nom                  : Optional[str]      = None
    prenom               : Optional[str]      = None
    email                : Optional[str]      = None
    identifiant_national : Optional[str]      = None
    username             : Optional[str]      = None
    statut               : str
    derniere_connexion   : Optional[datetime] = None
    nb_profils           : Optional[int]      = None
