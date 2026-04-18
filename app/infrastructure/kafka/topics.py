class Topics:
    """
    Topics Kafka publiés et consommés par IAM Local.
    Convention : iam.entite.evenement
    """

    # ── Topics consommés (depuis autres modules) ───────────────
    SCOLARITE_INSCRIPTION_SOUMISE = "scolarite.inscription.soumise"

    # ── Topics d'enregistrement (depuis tous les modules) ──────
    IAM_REGISTRATION_PERMISSIONS = "iam.registration.permissions"
    IAM_REGISTRATION_ENDPOINTS   = "iam.registration.endpoints"

    # ── Profils ────────────────────────────────────────────
    IAM_PROFIL_CREE      = "iam.profil.cree"
    IAM_PROFIL_MODIFIE   = "iam.profil.modifie"
    IAM_PROFIL_SUSPENDU  = "iam.profil.suspendu"
    IAM_PROFIL_REACTIVÉ  = "iam.profil.reactive"
    IAM_PROFIL_ERREUR    = "iam.profil.erreur"

    # ── Permissions ────────────────────────────────────────
    IAM_PERMISSION_CREEE    = "iam.permission.creee"
    IAM_PERMISSION_MODIFIEE = "iam.permission.modifiee"
    IAM_PERMISSION_DEPRECEE = "iam.permission.deprecee"

    # ── Rôles ──────────────────────────────────────────────
    IAM_ROLE_CREE    = "iam.role.cree"
    IAM_ROLE_MODIFIE = "iam.role.modifie"
    IAM_ROLE_SUPPRIME= "iam.role.supprime"

    # ── Groupes ────────────────────────────────────────────
    IAM_GROUPE_CREE          = "iam.groupe.cree"
    IAM_GROUPE_MODIFIE       = "iam.groupe.modifie"
    IAM_GROUPE_SUPPRIME      = "iam.groupe.supprime"
    IAM_GROUPE_MEMBRE_AJOUTE = "iam.groupe.membre_ajoute"
    IAM_GROUPE_MEMBRE_RETIRE = "iam.groupe.membre_retire"

    # ── Assignations ───────────────────────────────────────
    IAM_ROLE_ASSIGNE  = "iam.assignation.role_assigne"
    IAM_ROLE_REVOQUE  = "iam.assignation.role_revoque"

    # ── Délégations ────────────────────────────────────────
    IAM_DELEGATION_CREEE    = "iam.delegation.creee"
    IAM_DELEGATION_REVOQUEE = "iam.delegation.revoquee"
    IAM_DELEGATION_EXPIREE  = "iam.delegation.expiree"

    # ── Auth ───────────────────────────────────────────────
    IAM_CONNEXION    = "iam.auth.connexion"
    IAM_DECONNEXION  = "iam.auth.deconnexion"
    IAM_ECHEC_AUTH   = "iam.auth.echec"

    # ── Habilitations ──────────────────────────────────────
    IAM_ACCES_REFUSE = "iam.habilitation.acces_refuse"
