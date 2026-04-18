"""
Service de gestion des comptes locaux.

Le CompteLocal représente l'identité consolidée d'un utilisateur dans
l'établissement. Il est le seul porteur du lien vers IAM Central.

Ce service gère :
  - La création/synchronisation des comptes via SSO IAM Central
  - La création manuelle de comptes (bootstrap, admin)
  - La suspension/réactivation des comptes
  - La recherche et consultation des comptes

La gestion des credentials locaux (mot de passe) reste dans
CredentialService mais opère désormais sur CompteLocal.
"""
from uuid import UUID
from typing import Optional, List
from datetime import datetime, timezone
from sqlalchemy.ext.asyncio import AsyncSession

from app.repositories.compte_local import CompteLocalRepository
from app.schemas.compte_local import (
    CompteLocalCreateSchema,
    CompteLocalAvecCredentialsCreateSchema,
    CompteLocalUpdateSchema,
    CompteSyncSchema,
    SuspendreCompteSchema,
    CompteLocalResponseSchema,
    CompteLocalListSchema,
)
from app.core.exceptions import (
    NotFoundError,
    AlreadyExistsError,
    ValidationError,
)
from app.services.audit_service import AuditService
from app.infrastructure.kafka.producer import KafkaProducer
from app.infrastructure.kafka.topics import Topics
import logging

logger = logging.getLogger(__name__)


class CompteLocalService:

    def __init__(self, db: AsyncSession):
        self.db      = db
        self.repo    = CompteLocalRepository(db)
        self.audit   = AuditService(db)
        self.producer = KafkaProducer()

    # ── Synchronisation SSO ───────────────────────────────

    async def get_ou_creer(
        self,
        sync_data  : CompteSyncSchema,
        ip_address : Optional[str] = None,
        user_agent : Optional[str] = None,
        request_id : Optional[str] = None,
    ):
        """
        Appelé à chaque connexion via IAM Central (SSO).
        Crée le compte s'il n'existe pas (lazy creation),
        puis synchronise les données depuis IAM Central.

        Retourne l'objet CompteLocal (modèle ORM).
        """
        compte = await self.repo.get_by_user_id_national(
            sync_data.user_id_national
        )
        now = datetime.now(timezone.utc)

        if not compte:
            # Première connexion — créer le compte local
            compte = await self.repo.create({
                "user_id_national"    : sync_data.user_id_national,
                "nom"                 : sync_data.nom,
                "prenom"              : sync_data.prenom,
                "email"               : sync_data.email,
                "telephone"           : sync_data.telephone,
                "identifiant_national": sync_data.identifiant_national,
                "statut"              : "actif",
                "premiere_connexion"  : now,
                "derniere_connexion"  : now,
                "nb_connexions"       : "1",
                "snapshot_iam_central": sync_data.snapshot_iam_central,
            })

            await self.producer.publish(
                topic   = Topics.IAM_PROFIL_CREE,
                payload = {
                    "compte_id"        : str(compte.id),
                    "user_id_national" : str(compte.user_id_national),
                },
            )

        else:
            # Connexion suivante — vérifier statut
            if compte.statut == "suspendu":
                raise ValidationError(
                    f"Votre accès est suspendu. "
                    f"Raison : {compte.raison_suspension}"
                )

            # Synchroniser les données IAM Central
            nb = int(compte.nb_connexions or "0") + 1
            compte = await self.repo.update(compte, {
                "nom"                 : sync_data.nom,
                "prenom"              : sync_data.prenom,
                "email"               : sync_data.email,
                "telephone"           : sync_data.telephone,
                "identifiant_national": sync_data.identifiant_national,
                "derniere_connexion"  : now,
                "nb_connexions"       : str(nb),
                "snapshot_iam_central": sync_data.snapshot_iam_central,
            })

        return compte

    # ── Création manuelle ─────────────────────────────────

    async def creer_manuel(
        self,
        data       : CompteLocalCreateSchema,
        cree_par   : UUID,
        request_id : Optional[str] = None,
    ) -> CompteLocalResponseSchema:
        """
        Crée un compte local manuellement (sans SSO).
        Utilisé pour le bootstrap ou les comptes externes.
        """
        if data.user_id_national:
            existant = await self.repo.get_by_user_id_national(
                data.user_id_national
            )
            if existant:
                raise AlreadyExistsError(
                    "CompteLocal", "user_id_national",
                    str(data.user_id_national)
                )

        now = datetime.now(timezone.utc)
        compte = await self.repo.create({
            "user_id_national"    : data.user_id_national,
            "nom"                 : data.nom,
            "prenom"              : data.prenom,
            "email"               : data.email,
            "telephone"           : data.telephone,
            "identifiant_national": data.identifiant_national,
            "statut"              : "actif",
            "premiere_connexion"  : now,
            "nb_connexions"       : "0",
            "meta_data"           : data.meta_data or {},
            "notes"               : data.notes,
            "created_by"          : cree_par,
        })

        await self.audit.log(
            type_action = "compte_cree_manuel",
            profil_id   = None,
            module      = "iam",
            ressource   = "compte_local",
            action      = "creer",
            autorise    = True,
            raison      = "Création manuelle",
            request_id  = request_id,
        )

        return self._to_response(compte)

    async def creer_avec_credentials(
        self,
        data       : CompteLocalAvecCredentialsCreateSchema,
        cree_par   : UUID,
        request_id : Optional[str] = None,
    ):
        """
        Crée un compte local avec credentials pour authentification locale.
        Retourne l'objet ORM CompteLocal (pour le bootstrap).
        """
        # Vérifications d'unicité
        if await self.repo.get_by_username(data.username):
            raise AlreadyExistsError("CompteLocal", "username", data.username)
        if data.identifiant_national:
            if await self.repo.get_by_identifiant_national(data.identifiant_national):
                raise AlreadyExistsError(
                    "CompteLocal", "identifiant_national", data.identifiant_national
                )
        if data.email:
            if await self.repo.get_by_email(data.email):
                raise AlreadyExistsError("CompteLocal", "email", data.email)

        # Hash du mot de passe
        from app.services.credential_service import CredentialService
        cred_svc = CredentialService(self.db)
        password_hash, password_salt = cred_svc.hash_password(data.password)

        now = datetime.now(timezone.utc)
        compte = await self.repo.create({
            "user_id_national"      : None,
            "nom"                   : data.nom,
            "prenom"                : data.prenom,
            "email"                 : data.email,
            "telephone"             : data.telephone,
            "identifiant_national"  : data.identifiant_national,
            "username"              : data.username,
            "statut"                : "actif",
            "nb_connexions"         : "0",
            "password_hash"         : password_hash,
            "password_salt"         : password_salt,
            "password_algorithm"    : "bcrypt",
            "password_changed_at"   : now,
            "require_password_change": data.require_password_change,
            "meta_data"             : data.meta_data or {},
            "notes"                 : data.notes,
            "created_by"            : cree_par,
        })

        await self.audit.log(
            type_action = "compte_cree_avec_credentials",
            profil_id   = None,
            module      = "iam",
            ressource   = "compte_local",
            action      = "creer",
            autorise    = True,
            raison      = "Création avec credentials locales",
            request_id  = request_id,
        )

        return compte

    # ── Consultation ──────────────────────────────────────

    async def get_by_id(self, id: UUID) -> CompteLocalResponseSchema:
        compte = await self.repo.get_by_id(id)
        if not compte:
            raise NotFoundError("CompteLocal", str(id))
        return self._to_response(compte)

    async def get_with_profils(self, id: UUID) -> CompteLocalResponseSchema:
        compte = await self.repo.get_with_profils(id)
        if not compte:
            raise NotFoundError("CompteLocal", str(id))
        resp = self._to_response(compte)
        resp.nb_profils = len([p for p in compte.profils if not p.is_deleted])
        return resp

    async def get_all(
        self,
        skip   : int           = 0,
        limit  : int           = 50,
        statut : Optional[str] = None,
        q      : Optional[str] = None,
    ) -> List[CompteLocalListSchema]:
        if q:
            items = await self.repo.search(q)
        elif statut:
            items = await self.repo.get_by_statut(statut)
        else:
            items = await self.repo.get_all(skip=skip, limit=limit)
        return [self._to_list(c) for c in items]

    # ── Modification ──────────────────────────────────────

    async def update(
        self,
        id         : UUID,
        data       : CompteLocalUpdateSchema,
        updated_by : UUID,
    ) -> CompteLocalResponseSchema:
        compte = await self.repo.get_by_id(id)
        if not compte:
            raise NotFoundError("CompteLocal", str(id))

        update_data = {
            k: v for k, v in data.model_dump().items() if v is not None
        }
        update_data["updated_by"] = updated_by
        compte = await self.repo.update(compte, update_data)
        return self._to_response(compte)

    async def suspendre(
        self,
        id         : UUID,
        data       : SuspendreCompteSchema,
        suspend_by : UUID,
        request_id : Optional[str] = None,
    ) -> CompteLocalResponseSchema:
        compte = await self.repo.get_by_id(id)
        if not compte:
            raise NotFoundError("CompteLocal", str(id))
        if compte.statut == "suspendu":
            raise ValidationError("Ce compte est déjà suspendu.")

        compte = await self.repo.update(compte, {
            "statut"           : "suspendu",
            "raison_suspension": data.raison,
            "updated_by"       : suspend_by,
        })

        await self.audit.log(
            type_action = "compte_suspendu",
            profil_id   = None,
            module      = "iam",
            ressource   = "compte_local",
            action      = "suspendre",
            autorise    = True,
            raison      = data.raison,
            request_id  = request_id,
        )

        await self.producer.publish(
            topic   = Topics.IAM_PROFIL_SUSPENDU,
            payload = {
                "compte_id"  : str(compte.id),
                "raison"     : data.raison,
                "suspend_by" : str(suspend_by),
            },
        )
        return self._to_response(compte)

    async def reactiver(
        self,
        id         : UUID,
        updated_by : UUID,
    ) -> CompteLocalResponseSchema:
        compte = await self.repo.get_by_id(id)
        if not compte:
            raise NotFoundError("CompteLocal", str(id))
        compte = await self.repo.update(compte, {
            "statut"           : "actif",
            "raison_suspension": None,
            "updated_by"       : updated_by,
        })
        return self._to_response(compte)

    async def supprimer(
        self,
        id         : UUID,
        deleted_by : UUID,
        request_id : Optional[str] = None,
    ) -> None:
        compte = await self.repo.get_by_id(id)
        if not compte:
            raise NotFoundError("CompteLocal", str(id))
        if compte.username == "bootstrap":
            raise ValidationError(
                "Le compte bootstrap ne peut pas être supprimé directement."
            )
        await self.repo.soft_delete(compte, deleted_by)

        await self.audit.log(
            type_action = "compte_supprime",
            profil_id   = None,
            module      = "iam",
            ressource   = "compte_local",
            action      = "supprimer",
            autorise    = True,
            raison      = "Suppression par administrateur",
            request_id  = request_id,
        )

    # ── Helpers internes ─────────────────────────────────

    def _to_response(self, compte) -> CompteLocalResponseSchema:
        return CompteLocalResponseSchema(
            id                      = compte.id,
            created_at              = compte.created_at,
            updated_at              = compte.updated_at,
            created_by              = compte.created_by,
            updated_by              = compte.updated_by,
            user_id_national        = compte.user_id_national,
            nom                     = compte.nom,
            prenom                  = compte.prenom,
            email                   = compte.email,
            telephone               = compte.telephone,
            identifiant_national    = compte.identifiant_national,
            username                = compte.username,
            statut                  = compte.statut,
            raison_suspension       = compte.raison_suspension,
            derniere_connexion      = compte.derniere_connexion,
            nb_connexions           = compte.nb_connexions,
            premiere_connexion      = compte.premiere_connexion,
            require_password_change = compte.require_password_change,
            preferences             = compte.preferences or {},
            meta_data               = compte.meta_data or {},
            notes                   = compte.notes,
            has_credentials         = compte.password_hash is not None,
        )

    def _to_list(self, compte) -> CompteLocalListSchema:
        return CompteLocalListSchema(
            id                   = compte.id,
            created_at           = compte.created_at,
            updated_at           = compte.updated_at,
            user_id_national     = compte.user_id_national,
            nom                  = compte.nom,
            prenom               = compte.prenom,
            email                = compte.email,
            identifiant_national = compte.identifiant_national,
            username             = compte.username,
            statut               = compte.statut,
            derniere_connexion   = compte.derniere_connexion,
        )
