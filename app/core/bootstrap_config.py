"""
Constantes du système de bootstrap IAM Local.
Ces valeurs sont utilisées par le script d'installation
et par les guards de sécurité pour identifier le profil temporaire.
"""

# ── Identité du profil bootstrap ──────────────────────────
BOOTSTRAP_IDENTIFIANT    = "BOOTSTRAP_ADMIN"
BOOTSTRAP_NOM            = "Administrateur"
BOOTSTRAP_PRENOM         = "Bootstrap"
BOOTSTRAP_EMAIL          = "bootstrap@system.local"
BOOTSTRAP_TYPE_PROFIL    = "systeme"
BOOTSTRAP_STATUT         = "bootstrap"

# ── Rôle temporaire ───────────────────────────────────────
ROLE_TEMP_CODE           = "iam.admin_temp"
ROLE_TEMP_LIBELLE        = "Administrateur Temporaire Bootstrap"
ROLE_TEMP_DESCRIPTION    = (
    "Rôle temporaire créé au bootstrap. "
    "Contient uniquement les permissions nécessaires "
    "à la création du premier administrateur réel. "
    "Doit être supprimé après installation."
)

# ── Source IAM ────────────────────────────────────────────
IAM_SOURCE_CODE          = "iam-local"
IAM_SOURCE_NOM           = "IAM Local"
IAM_SOURCE_VERSION       = "1.0.0"

# ── Groupe Super Admin ────────────────────────────────────
GROUPE_SUPER_ADMIN_CODE  = "super_admin"
GROUPE_SUPER_ADMIN_NOM   = "Super Administrateurs"

# ── Rôle admin complet ────────────────────────────────────
ROLE_ADMIN_CODE          = "iam.admin"
ROLE_ADMIN_LIBELLE       = "Administrateur IAM"

# ── Token bootstrap ───────────────────────────────────────
BOOTSTRAP_TOKEN_EXPIRE_HOURS = 48

# ── Permissions dans role_temp ────────────────────────────
# Ce sont des permissions ORDINAIRES — elles restent après bootstrap
# Elles sont "temp" uniquement parce qu'elles sont dans role_temp
# L'admin réel les utilisera aussi via ses rôles normaux
PERMISSIONS_ROLE_TEMP = [
    "iam.profil.creer",
    "iam.profil.consulter",
    "iam.profil.modifier",
    "iam.role.consulter",
    "iam.role.assigner",
    "iam.groupe.consulter",
    "iam.groupe.membre.ajouter",
]
