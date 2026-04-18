"""
Service d'authentification.

Deux flux d'authentification :
  1. authenticate_local()  → credentials locaux (username/password sur CompteLocal)
  2. creer_session()       → SSO via token IAM Central

Dans les deux cas, retourne user_data basé sur le ProfilLocal.
Le ProfilLocal est l'unité centrale : son id = sub du JWT, clé de session Redis.
La création de tokens JWT est EXCLUSIVEMENT faite par TokenManager.
"""
from uuid import UUID
from typing import Optional
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.schemas.profil_local import ProfilSyncSchema
from app.services.profil_service import ProfilService
from app.services.habilitation_service import HabilitationService
from app.services.credential_service import CredentialService
from app.services.bootstrap_cleanup_service import BootstrapCleanupService
from app.core.exceptions import TokenError, AuthenticationError
from app.core.bootstrap_config import ROLE_TEMP_CODE
import logging

logger = logging.getLogger(__name__)


class AuthService:
    """
    Gestion de l'authentification.

    - authenticate_local() : credentials → ProfilLocal → user_data pour TokenManager
    - creer_session()      : token IAM Central → ProfilLocal → user_data pour TokenManager

    user_data retourné :
        id               → profil.id       (sub du JWT, clé session Redis)
        username         → profil.username
        nom/prenom/email → depuis CompteLocal (dénormalisé dans ProfilResponseSchema)
        type_profil      → profil.type_profil
        statut           → profil.statut
        permissions/roles → calculés par HabilitationService sur profil.id
        user_id_national → compte.user_id_national (claim additionnel JWT)
    """

    def __init__(self, db: AsyncSession):
        self.db                   = db
        self.profil_service       = ProfilService(db)
        self.habilitation_service = HabilitationService(db)
        self.cleanup_service      = BootstrapCleanupService(db)
        self.credential_service   = CredentialService(db)

    # ── SSO IAM Central ───────────────────────────────────

    async def valider_token_iam_central(self, token: str) -> dict:
        """
        Valide le JWT émis par IAM Central.
        En production : vérification via JWKS endpoint.
        En développement : décodage avec secret partagé.
        """
        import jwt
        try:
            payload = jwt.decode(
                token,
                settings.JWT_SECRET_KEY,
                algorithms = [settings.JWT_ALGORITHM],
                options    = {"verify_exp": True},
            )
            return payload
        except jwt.ExpiredSignatureError:
            raise TokenError("Token IAM Central expiré.")
        except jwt.InvalidTokenError as e:
            raise TokenError(f"Token IAM Central invalide : {e}")

    async def creer_session(
        self,
        token_iam_central : str,
        ip_address        : Optional[str] = None,
        user_agent        : Optional[str] = None,
        request_id        : Optional[str] = None,
    ) -> dict:
        """
        Flux SSO complet :
          1. Valider le token IAM Central
          2. Extraire l'identité
          3. Synchroniser CompteLocal + résoudre/créer ProfilLocal
          4. Calculer les habilitations (sur profil.id)
          5. Retourner user_data pour TokenManager
          6. Déclencher nettoyage bootstrap si admin réel
        """
        # 1. Valider le token IAM Central
        payload = await self.valider_token_iam_central(token_iam_central)

        # 2. Extraire l'identité
        user_id_national = UUID(payload.get("sub"))
        if not user_id_national:
            raise TokenError("Token sans identifiant utilisateur.")

        sync_data = ProfilSyncSchema(
            user_id_national     = user_id_national,
            nom                  = payload.get("nom", ""),
            prenom               = payload.get("prenom", ""),
            email                = payload.get("email", ""),
            telephone            = payload.get("telephone"),
            identifiant_national = payload.get("identifiant_national"),
            type_profil          = payload.get("type_profil"),
            snapshot_iam_central = payload,
        )

        # 3. Synchroniser CompteLocal + résoudre ProfilLocal actif
        profil = await self.profil_service.get_ou_creer(
            sync_data  = sync_data,
            ip_address = ip_address,
            user_agent = user_agent,
            request_id = request_id,
        )

        # 4. Calculer les habilitations sur le profil
        habilitations = await self.habilitation_service.get_habilitations(profil.id)

        # 5. Construire user_data pour TokenManager
        #    sub = profil.id  → unité centrale de tout le système
        user_data = {
            "id"                      : profil.id,
            "username"                : profil.username or str(profil.id),
            "nom"                     : profil.compte_nom,
            "prenom"                  : profil.compte_prenom,
            "email"                   : profil.compte_email,
            "type_profil"             : profil.type_profil,
            "statut"                  : profil.statut,
            "permissions"             : [str(p.id) for p in habilitations.permissions if p.id],
            "permission_codes"        : [p.code for p in habilitations.permissions],
            "roles"                   : habilitations.roles_actifs,
            "groupes"                 : habilitations.groupes_actifs,
            "is_admin"                : "iam.admin" in habilitations.roles_actifs,
            "require_password_change" : False,  # SSO : géré par IAM Central
            "user_id_national"        : str(user_id_national),
            "compte_id"               : str(profil.compte_id),
        }

        # 6. Nettoyage bootstrap si admin réel
        await self._verifier_nettoyage_bootstrap(
            profil_id    = profil.id,
            roles_actifs = habilitations.roles_actifs,
        )

        return user_data

    # ── Auth locale ───────────────────────────────────────

    async def authenticate_local(
        self,
        username : str,
        password : str,
    ) -> dict:
        """
        Authentification locale avec credentials sur CompteLocal.
        Retourne user_data pour TokenManager — pas de JWT ici.
        """
        # 1. Authentifier via credentials → (CompteLocal, ProfilLocal)
        compte, profil = await self.credential_service.authenticate_credentials(
            identifier = username,
            password   = password,
        )

        # 2. Vérifier statut du profil
        if profil.statut != "actif":
            raise AuthenticationError(f"Profil {profil.statut}")

        # 3. Vérifier statut du compte
        if compte.statut != "actif" and compte.statut != "bootstrap":
            raise AuthenticationError(f"Compte {compte.statut}")

        # 4. Habilitations calculées sur profil.id
        habilitations = await self.habilitation_service.get_habilitations(profil.id)

        is_bootstrap = (compte.statut == "bootstrap")

        # 5. user_data pour TokenManager
        user_data = {
            "id"                      : profil.id,
            "username"                : profil.username or compte.username,
            "nom"                     : compte.nom,
            "prenom"                  : compte.prenom,
            "email"                   : compte.email,
            "type_profil"             : profil.type_profil,
            "statut"                  : profil.statut,
            "permissions"             : [str(p.id) for p in habilitations.permissions if p.id],
            "permission_codes"        : [p.code for p in habilitations.permissions],
            "roles"                   : habilitations.roles_actifs,
            "groupes"                 : habilitations.groupes_actifs,
            "is_admin"                : "iam.admin" in habilitations.roles_actifs,
            "require_password_change" : compte.require_password_change,
            "user_id_national"        : str(compte.user_id_national) if compte.user_id_national else None,
            "compte_id"               : str(compte.id),
            "is_bootstrap"            : is_bootstrap,
        }

        logger.info(f"Authentification locale réussie pour {username}")
        return user_data

    # ── Bootstrap cleanup ─────────────────────────────────

    async def _verifier_nettoyage_bootstrap(
        self,
        profil_id    : UUID,
        roles_actifs : list,
    ) -> None:
        try:
            if ROLE_TEMP_CODE in roles_actifs:
                return
            if "iam.admin" not in roles_actifs:
                return
            nettoye = await self.cleanup_service.verifier_et_nettoyer(
                profil_connecte_id    = profil_id,
                profil_connecte_roles = roles_actifs,
            )
            if nettoye:
                logger.warning(
                    f"🔐 SÉCURITÉ — Bootstrap supprimé automatiquement "
                    f"après connexion admin réel [profil={profil_id}]"
                )
        except Exception as e:
            logger.error(f"Bootstrap cleanup error (non bloquant) : {e}")
