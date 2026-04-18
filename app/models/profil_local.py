from sqlalchemy import Column, String, Text, Boolean, DateTime, Integer, ForeignKey
from sqlalchemy.dialects.postgresql import UUID, JSONB
from sqlalchemy.orm import relationship
from app.models.base import BaseModel


class ProfilLocal(BaseModel):
    """
    Profil applicatif local d'un utilisateur.

    Représente UNE INSCRIPTION / UN DOSSIER SCOLAIRE d'un utilisateur
    dans l'établissement. C'est L'UNITÉ DE BASE de toutes les opérations
    locales : tokens JWT, sessions Redis, permissions, rôles, audit.

    Un utilisateur (CompteLocal) peut avoir PLUSIEURS ProfilLocal,
    chacun correspondant à une inscription dans une filière distincte.

    Exemples :
        CompteLocal (Koffi ASSOUMOU)
            └── ProfilLocal → Inscription L1-Informatique  (type: etudiant)
            └── ProfilLocal → Inscription DUT-Réseaux      (type: etudiant)

        CompteLocal (Dr. Mireille ONDO)
            └── ProfilLocal → Enseignante Informatique     (type: enseignant)
            └── ProfilLocal → Chercheuse Labo IA           (type: enseignant_chercheur)

    TOKENS / SESSIONS :
    sub (JWT) = profil.id     → le token identifie un profil, pas un compte
    Sessions Redis liées à profil.id

    PERMISSIONS / RÔLES :
    Assignés au niveau du profil — granularité par inscription/dossier.

    AUDIT :
    Les actions dans les services métier sont tracées via profil.id.

    LIEN IAM CENTRAL :
    N'est PAS directement lié à IAM Central.
    Passe par CompteLocal (compte.user_id_national) pour remonter
    à l'identité nationale.

    NE CONTIENT PAS de credentials (gérés par CompteLocal).

    EXCEPTION BOOTSTRAP :
    Le profil temporaire de bootstrap est rattaché au CompteLocal bootstrap.
    Identifiable via compte.statut='bootstrap'.
    Doit être supprimé dès que l'admin réel est créé.
    """
    __tablename__ = "profils_locaux"

    # ── Lien vers le CompteLocal parent ───────────────────
    compte_id = Column(
        UUID(as_uuid=True),
        ForeignKey("comptes_locaux.id", ondelete="CASCADE"),
        nullable = False,
        index    = True,
        comment  = (
            "CompteLocal auquel appartient ce profil. "
            "C'est le compte qui porte l'identité et le lien IAM Central."
        )
    )

    # ── Identifiant de connexion locale ───────────────────
    # Hérité du CompteLocal mais dénormalisé ici pour la compatibilité
    # avec l'authentification locale et les services existants.
    # Unique par profil (format : prenom.nom.id_national[.index])
    username = Column(
        String(150),
        nullable = True,
        unique   = True,
        index    = True,
        comment  = "Identifiant de connexion locale — dénormalisé depuis CompteLocal"
    )

    # ── Type de profil / rôle académique ──────────────────
    # etudiant | enseignant | enseignant_chercheur |
    # personnel_admin | personnel_technique | direction | invite | systeme
    type_profil = Column(
        String(50),
        nullable = False,
        default  = "invite",
        index    = True,
    )

    # ── Statut de ce profil ───────────────────────────────
    # actif      → profil opérationnel
    # inactif    → désactivé manuellement
    # suspendu   → suspendu avec motif
    # expire     → profil expiré (ex : fin d'inscription)
    # bootstrap  → profil temporaire d'installation (DOIT ÊTRE SUPPRIMÉ)
    statut = Column(
        String(20),
        nullable       = False,
        default        = "actif",
        server_default = "actif",
        index          = True,
    )

    raison_suspension = Column(Text, nullable=True)

    # ── Métadonnées de session ─────────────────────────────
    # Suivies au niveau du profil car un même compte peut avoir
    # plusieurs profils avec des historiques de connexion distincts.
    derniere_connexion = Column(DateTime(timezone=True), nullable=True)
    nb_connexions      = Column(String(20), nullable=True, default="0")
    premiere_connexion = Column(DateTime(timezone=True), nullable=True)

    # ── Contexte scolaire / métier de ce profil ───────────
    # Données spécifiques à cette inscription ou ce rôle.
    # ex : filière, composante, département, année académique...
    contexte_scolaire = Column(
        JSONB,
        nullable = True,
        default  = dict,
        comment  = (
            "Contexte métier propre à ce profil : "
            "{filiere, composante, departement, annee_academique, "
            "niveau, specialite, numero_etudiant_local, ...}"
        )
    )

    # ── Préférences locales spécifiques au profil ─────────
    preferences = Column(
        JSONB,
        nullable = True,
        default  = dict,
        comment  = "Préférences UI spécifiques à ce profil"
    )

    meta_data = Column(JSONB, nullable=True, default=dict)
    notes     = Column(Text,  nullable=True)

    # ── Relations ─────────────────────────────────────────
    compte = relationship(
        "CompteLocal",
        back_populates = "profils",
        lazy           = "select",
    )
    assignations_role = relationship(
        "AssignationRole",
        back_populates = "profil",
        lazy           = "select",
    )
    assignations_groupe = relationship(
        "AssignationGroupe",
        back_populates = "profil",
        lazy           = "select",
    )
    delegations_accordees = relationship(
        "Delegation",
        foreign_keys   = "Delegation.delegant_id",
        back_populates = "delegant",
        lazy           = "select",
    )
    delegations_recues = relationship(
        "Delegation",
        foreign_keys   = "Delegation.delegataire_id",
        back_populates = "delegataire",
        lazy           = "select",
    )
