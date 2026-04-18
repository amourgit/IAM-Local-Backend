import enum


class StatutProfil(str, enum.Enum):
    ACTIF      = "actif"
    INACTIF    = "inactif"
    SUSPENDU   = "suspendu"
    EXPIRE     = "expire"


class TypeProfil(str, enum.Enum):
    ETUDIANT        = "etudiant"
    ENSEIGNANT      = "enseignant"
    ENSEIGNANT_CHERCHEUR = "enseignant_chercheur"
    PERSONNEL_ADMIN = "personnel_admin"
    PERSONNEL_TECHNIQUE = "personnel_technique"
    DIRECTION       = "direction"
    INVITE          = "invite"
    SYSTEME         = "systeme"


class TypeRole(str, enum.Enum):
    FONCTIONNEL    = "fonctionnel"
    ADMINISTRATIF  = "administratif"
    TECHNIQUE      = "technique"
    TEMPORAIRE     = "temporaire"
    SYSTEME        = "systeme"


class TypeGroupe(str, enum.Enum):
    FONCTIONNEL    = "fonctionnel"
    ORGANISATIONNEL= "organisationnel"
    PROJET         = "projet"
    TECHNIQUE      = "technique"


class NiveauRisque(str, enum.Enum):
    FAIBLE    = "faible"
    MOYEN     = "moyen"
    ELEVE     = "eleve"
    CRITIQUE  = "critique"


class StatutAssignation(str, enum.Enum):
    ACTIVE    = "active"
    SUSPENDUE = "suspendue"
    EXPIREE   = "expiree"
    REVOQUEE  = "revoquee"


class StatutDelegation(str, enum.Enum):
    ACTIVE    = "active"
    EXPIREE   = "expiree"
    REVOQUEE  = "revoquee"


class TypeAction(str, enum.Enum):
    # Auth
    CONNEXION          = "connexion"
    DECONNEXION        = "deconnexion"
    ECHEC_AUTH         = "echec_auth"
    # Permissions
    ACCES_AUTORISE     = "acces_autorise"
    ACCES_REFUSE       = "acces_refuse"
    # Administration
    ROLE_ASSIGNE       = "role_assigne"
    ROLE_REVOQUE       = "role_revoque"
    GROUPE_REJOINT     = "groupe_rejoint"
    GROUPE_QUITTE      = "groupe_quitte"
    DELEGATION_CREEE   = "delegation_creee"
    DELEGATION_REVOQUEE= "delegation_revoquee"
    PROFIL_CREE        = "profil_cree"
    PROFIL_MODIFIE     = "profil_modifie"
    PROFIL_SUSPENDU    = "profil_suspendu"
    PERMISSION_CREEE   = "permission_creee"
    PERMISSION_MODIFIEE= "permission_modifiee"


class DomainePermission(str, enum.Enum):
    """
    Domaines fonctionnels connus.
    Extensible — chaque nouveau microservice
    déclare son domaine à l'enregistrement.
    """
    ORG         = "org"
    SCOLARITE   = "scolarite"
    RH          = "rh"
    FINANCE     = "finance"
    PEDAGOGIQUE = "pedagogique"
    RECHERCHE   = "recherche"
    BIBLIOTHEQUE= "bibliotheque"
    SYSTEME     = "systeme"
    IAM         = "iam"
