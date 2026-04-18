from sqlalchemy import Column, String, Text, Boolean, DateTime, Integer
from sqlalchemy.dialects.postgresql import UUID, JSONB
from sqlalchemy.orm import relationship
from app.models.base import BaseModel


class CompteLocal(BaseModel):
    """
    Compte local d'un utilisateur dans l'établissement.

    Représente l'identité consolidée d'UN utilisateur au niveau
    de l'établissement. Créé automatiquement à la première connexion
    via IAM Central (lazy creation / SSO), ou manuellement pour les
    profils à authentification locale.

    RÔLE CENTRAL :
    Le CompteLocal est le seul point de vérité local concernant
    l'identité de l'utilisateur et son lien avec IAM Central.
    Il peut avoir PLUSIEURS ProfilLocal (ex : un étudiant inscrit
    dans deux filières simultanément dans le même établissement).

    LIEN IAM CENTRAL :
    - user_id_national     → UUID officiel dans IAM Central (unique)
    - identifiant_national → Numéro étudiant/matricule officiel (unique)
    - snapshot_iam_central → Copie des données reçues lors du SSO

    AUTHENTIFICATION :
    - Via IAM Central (SSO) : aucun mot de passe local nécessaire
    - Via credentials locaux : password_hash/salt stockés ici

    EXCEPTION BOOTSTRAP :
    Le compte temporaire de bootstrap a user_id_national=NULL.
    Identifiable par statut='bootstrap' et
    identifiant_national='BOOTSTRAP_ADMIN'.
    Il DOIT être supprimé dès que l'admin réel est créé.
    """
    __tablename__ = "comptes_locaux"

    # ── Lien IAM Central ──────────────────────────────────
    user_id_national = Column(
        UUID(as_uuid=True),
        nullable = True,           # NULL autorisé uniquement pour bootstrap
        unique   = True,
        index    = True,
        comment  = (
            "UUID de l'utilisateur dans IAM Central. "
            "NULL uniquement pour le compte bootstrap temporaire."
        )
    )

    # ── Informations copiées depuis IAM Central ────────────
    # Source de vérité : synchronisées à chaque connexion SSO.
    nom       = Column(String(255), nullable=True)
    prenom    = Column(String(255), nullable=True)
    email     = Column(String(255), nullable=True, index=True)
    telephone = Column(String(50),  nullable=True)

    # Identifiant national éducatif officiel
    # Valeur spéciale : "BOOTSTRAP_ADMIN" pour le compte temporaire
    identifiant_national = Column(String(100), nullable=True, index=True)

    # Identifiant de connexion locale (généré automatiquement)
    # Format : prenom.nom.id_national
    username = Column(
        String(150),
        nullable = True,
        unique   = True,
        index    = True,
        comment  = "Identifiant de connexion locale généré automatiquement"
    )

    # ── Statut du compte ──────────────────────────────────
    # actif      → compte normal opérationnel
    # inactif    → désactivé manuellement
    # suspendu   → suspendu avec motif
    # expire     → accès expiré
    # bootstrap  → compte temporaire d'installation (DOIT ÊTRE SUPPRIMÉ)
    statut = Column(
        String(20),
        nullable       = False,
        default        = "actif",
        server_default = "actif",
        index          = True,
    )

    raison_suspension = Column(Text, nullable=True)

    # ── Métadonnées de connexion ──────────────────────────
    derniere_connexion = Column(DateTime(timezone=True), nullable=True)
    nb_connexions      = Column(String(20), nullable=True, default="0")
    premiere_connexion = Column(DateTime(timezone=True), nullable=True)

    # ── Credentials locaux (auth locale, hors SSO) ────────
    # Utilisés uniquement pour les comptes sans SSO IAM Central.
    password_hash = Column(
        String(255),
        nullable = True,
        comment  = "Hash sécurisé du mot de passe local (bcrypt)"
    )
    password_salt = Column(
        String(255),
        nullable = True,
        comment  = "Sel cryptographique pour le hash"
    )
    password_algorithm = Column(
        String(50),
        nullable = True,
        default  = "bcrypt",
        comment  = "Algorithme de hash : bcrypt, argon2, pbkdf2..."
    )
    password_changed_at = Column(
        DateTime(timezone=True),
        nullable = True,
        comment  = "Date du dernier changement de mot de passe"
    )

    # Sécurité : tentatives de connexion échouées
    failed_login_attempts = Column(
        Integer,
        nullable       = False,
        default        = 0,
        comment        = "Nombre de tentatives de connexion échouées"
    )

    # Sécurité : verrouillage temporaire du compte
    locked_until = Column(
        DateTime(timezone=True),
        nullable = True,
        comment  = "Date jusqu'à laquelle le compte est verrouillé"
    )

    # Forcer le changement de mot de passe à la prochaine connexion
    require_password_change = Column(
        Boolean,
        nullable = False,
        default  = False,
        comment  = "Le compte doit changer son mot de passe à la prochaine connexion"
    )

    # ── Snapshot IAM Central ─────────────────────────────
    # Données brutes reçues lors du dernier SSO.
    # Permet un fonctionnement dégradé si IAM Central est indisponible.
    snapshot_iam_central = Column(
        JSONB,
        nullable = True,
        comment  = (
            "Snapshot complet des données IAM Central "
            "au moment de la dernière synchronisation SSO. "
            "NULL pour le compte bootstrap."
        )
    )

    # ── Préférences locales ───────────────────────────────
    preferences = Column(
        JSONB,
        nullable = True,
        default  = dict,
        comment  = "Préférences UI, langue, notifications..."
    )

    meta_data = Column(JSONB, nullable=True, default=dict)
    notes     = Column(Text,  nullable=True)

    # ── Relations ─────────────────────────────────────────
    profils = relationship(
        "ProfilLocal",
        back_populates = "compte",
        lazy           = "select",
        cascade        = "all, delete-orphan",
    )
