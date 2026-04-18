from typing import Optional, Any
from uuid import UUID
from datetime import datetime
from pydantic import Field
from app.schemas.base import BaseSchema, BaseResponseSchema
from app.core.enums import TypeProfil, StatutProfil


# ─────────────────────────────────────────────────────────────
#  CREATE
# ─────────────────────────────────────────────────────────────

class ProfilLocalCreateSchema(BaseSchema):
    """
    Création d'un profil local rattaché à un CompteLocal existant.
    Utilisé pour créer une nouvelle inscription / un nouveau dossier
    scolaire pour un utilisateur déjà connu dans l'établissement.
    """
    compte_id         : UUID
    type_profil       : TypeProfil        = TypeProfil.INVITE
    contexte_scolaire : Optional[Any]     = {}
    meta_data         : Optional[Any]     = {}
    notes             : Optional[str]     = None


class ProfilLocalWithCredentialsCreateSchema(BaseSchema):
    """
    Création d'un compte local + profil en une seule opération,
    avec credentials pour authentification locale (hors SSO).
    Utilisé pour le bootstrap et les utilisateurs sans accès SSO.

    Crée automatiquement :
      1. Un CompteLocal avec les informations de base + credentials
      2. Un ProfilLocal de type demandé, rattaché au compte
    """
    # ── Informations du CompteLocal ──────────────────────
    nom                     : str
    prenom                  : str
    email                   : str
    telephone               : Optional[str] = None
    identifiant_national    : str            # Numéro étudiant/matricule
    username                : str            # Identifiant de connexion unique
    password                : str            # Mot de passe initial
    require_password_change : bool           = True

    # ── Informations du ProfilLocal ──────────────────────
    type_profil             : TypeProfil
    meta_data               : Optional[Any] = {}
    notes                   : Optional[str] = None

    # Contexte scolaire du profil (optionnel selon le type)
    classe          : Optional[str] = None   # Pour étudiants
    niveau          : Optional[str] = None   # Pour étudiants
    specialite      : Optional[str] = None   # Pour étudiants/enseignants
    annee_scolaire  : Optional[str] = None   # Pour étudiants


class ProfilSyncSchema(BaseSchema):
    """
    Payload de synchronisation depuis IAM Central (via CompteLocal).
    Utilisé en interne lors d'une connexion SSO pour :
      1. Synchroniser le CompteLocal avec les données IAM Central
      2. Résoudre/créer le ProfilLocal actif
    """
    user_id_national     : UUID
    nom                  : str
    prenom               : str
    email                : str
    telephone            : Optional[str] = None
    identifiant_national : Optional[str] = None
    type_profil          : Optional[str] = None
    snapshot_iam_central : Optional[Any] = None


# ─────────────────────────────────────────────────────────────
#  UPDATE
# ─────────────────────────────────────────────────────────────

class ProfilLocalUpdateSchema(BaseSchema):
    """Mise à jour manuelle d'un profil par un administrateur."""
    type_profil       : Optional[TypeProfil] = None
    contexte_scolaire : Optional[Any]        = None
    preferences       : Optional[Any]        = None
    meta_data         : Optional[Any]        = None
    notes             : Optional[str]        = None


class SuspendreProfilSchema(BaseSchema):
    raison : str = Field(..., min_length=5)


# ─────────────────────────────────────────────────────────────
#  RESPONSE
# ─────────────────────────────────────────────────────────────

class ProfilResponseSchema(BaseResponseSchema):
    """
    Réponse complète d'un profil local.
    Inclut les informations du CompteLocal parent pour
    les services métier qui ont besoin de l'identité complète.
    """
    compte_id          : UUID
    username           : Optional[str]      = None
    type_profil        : str
    statut             : str
    raison_suspension  : Optional[str]      = None
    derniere_connexion : Optional[datetime] = None
    nb_connexions      : Optional[str]      = None
    premiere_connexion : Optional[datetime] = None
    contexte_scolaire  : Optional[Any]      = {}
    preferences        : Optional[Any]      = {}
    meta_data          : Optional[Any]      = {}
    notes              : Optional[str]      = None

    # ── Informations du compte parent (dénormalisées pour les services) ──
    # Permettent aux services métier d'accéder à l'identité
    # sans avoir à faire une jointure supplémentaire.
    compte_nom                  : Optional[str]  = None
    compte_prenom               : Optional[str]  = None
    compte_email                : Optional[str]  = None
    compte_telephone            : Optional[str]  = None
    compte_identifiant_national : Optional[str]  = None
    compte_user_id_national     : Optional[UUID] = None
    require_password_change     : Optional[bool] = None


class ProfilListSchema(BaseResponseSchema):
    """Réponse allégée pour les listes."""
    compte_id          : UUID
    username           : Optional[str]  = None
    type_profil        : str
    statut             : str
    derniere_connexion : Optional[datetime] = None

    # Informations du compte parent
    compte_nom                  : Optional[str] = None
    compte_prenom               : Optional[str] = None
    compte_email                : Optional[str] = None
    compte_identifiant_national : Optional[str] = None
