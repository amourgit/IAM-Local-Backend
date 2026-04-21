"""
Service de gestion des profils locaux.

Le ProfilLocal est L'UNITÉ DE BASE de toutes les opérations locales :
tokens JWT, sessions Redis, permissions, rôles, audit.

Ce service gère :
  - La création de profils rattachés à un CompteLocal
  - La résolution du profil actif lors d'une connexion SSO
  - La suspension/réactivation des profils
  - L'assignation/révocation des rôles
  - La consultation et la recherche de profils

Les données d'identité (nom, prénom, email, etc.) sont portées par
le CompteLocal. Ce service les expose via dénormalisation pour les
services métier qui ont besoin de l'identité complète d'un profil.
"""
from uuid import UUID
from typing import Optional, List
from datetime import datetime, timezone
from sqlalchemy.ext.asyncio import AsyncSession

from app.repositories.profil_local import ProfilLocalRepository
from app.repositories.compte_local import CompteLocalRepository
from app.repositories.assignation_role import AssignationRoleRepository
from app.repositories.assignation_groupe import AssignationGroupeRepository
from app.schemas.profil_local import (
    ProfilLocalCreateSchema,
    ProfilLocalUpdateSchema,
    ProfilLocalWithCredentialsCreateSchema,
    ProfilSyncSchema,
    SuspendreProfilSchema,
    ProfilResponseSchema,
    ProfilListSchema,
)
from app.schemas.assignation import (
    AssignationRoleCreateSchema,
    AssignationRoleResponseSchema,
    RevoquerAssignationSchema,
)
from app.core.exceptions import (
    NotFoundError,
    AlreadyExistsError,
    ValidationError,
)
from app.services.audit_service import AuditService
from app.services.compte_local_service import CompteLocalService
from app.schemas.compte_local import (
    CompteLocalAvecCredentialsCreateSchema,
    CompteSyncSchema,
)
from app.infrastructure.kafka.producer import KafkaProducer
from app.infrastructure.kafka.topics import Topics
import logging

logger = logging.getLogger(__name__)


class ProfilService:

    def __init__(self, db: AsyncSession):
        self.db           = db
        self.repo         = ProfilLocalRepository(db)
        self.compte_repo  = CompteLocalRepository(db)
        self.assign_repo  = AssignationRoleRepository(db)
        self.audit        = AuditService(db)
        self.compte_svc   = CompteLocalService(db)
        self.producer     = KafkaProducer()

    # ── SSO : connexion via IAM Central ──────────────────

    async def get_ou_creer(
        self,
        sync_data  : ProfilSyncSchema,
        ip_address : Optional[str] = None,
        user_agent : Optional[str] = None,
        request_id : Optional[str] = None,
    ) -> ProfilResponseSchema:
        """
        Appelé à chaque connexion via IAM Central.

        Flux :
          1. Synchronise/crée le CompteLocal (identité + lien IAM Central)
          2. Résout le profil actif du compte (premier profil actif)
          3. Crée un profil par défaut si aucun n'existe encore
          4. Retourne le ProfilResponseSchema avec identité dénormalisée

        Le ProfilLocal retourné est celui dont l'id servira de `sub`
        dans le JWT et de clé pour les sessions Redis.
        """
        # 1. Synchroniser / créer le CompteLocal
        compte_sync = CompteSyncSchema(
            user_id_national     = sync_data.user_id_national,
            nom                  = sync_data.nom,
            prenom               = sync_data.prenom,
            email                = sync_data.email,
            telephone            = sync_data.telephone,
            identifiant_national = sync_data.identifiant_national,
            type_profil          = sync_data.type_profil,
            snapshot_iam_central = sync_data.snapshot_iam_central,
        )
        compte = await self.compte_svc.get_ou_creer(
            sync_data  = compte_sync,
            ip_address = ip_address,
            user_agent = user_agent,
            request_id = request_id,
        )

        now = datetime.now(timezone.utc)

        # 2. Chercher le profil actif du compte
        profil = await self._resoudre_profil_actif(compte.id)

        if not profil:
            # Première connexion dans cet établissement — créer le profil par défaut
            type_profil = sync_data.type_profil or "invite"
            profil = await self.repo.create({
                "compte_id"          : compte.id,
                "username"           : compte.username,
                "type_profil"        : type_profil,
                "statut"             : "actif",
                "premiere_connexion" : now,
                "derniere_connexion" : now,
                "nb_connexions"      : "1",
                "contexte_scolaire"  : {},
            })

            await self.audit.log_connexion(
                user_id_national = sync_data.user_id_national,
                profil_id        = profil.id,
                nom_affiche      = f"{sync_data.prenom} {sync_data.nom}",
                ip_address       = ip_address,
                user_agent       = user_agent,
                request_id       = request_id,
            )

            await self.producer.publish(
                topic   = Topics.IAM_PROFIL_CREE,
                payload = {
                    "profil_id"        : str(profil.id),
                    "compte_id"        : str(compte.id),
                    "user_id_national" : str(compte.user_id_national),
                    "type_profil"      : profil.type_profil,
                },
            )

        else:
            # Connexion suivante — mettre à jour les métadonnées de session
            nb = int(profil.nb_connexions or "0") + 1
            profil = await self.repo.update(profil, {
                "derniere_connexion" : now,
                "nb_connexions"      : str(nb),
            })

            await self.audit.log_connexion(
                user_id_national = sync_data.user_id_national,
                profil_id        = profil.id,
                nom_affiche      = f"{sync_data.prenom} {sync_data.nom}",
                ip_address       = ip_address,
                user_agent       = user_agent,
                request_id       = request_id,
            )

        return self._to_response(profil, compte)

    async def _resoudre_profil_actif(self, compte_id: UUID):
        """
        Résout le profil actif principal d'un compte.
        Retourne le premier profil actif (par date de création).
        Retourne None si aucun profil n'existe encore.
        """
        profils = await self.repo.get_actif_by_compte_id(compte_id)
        return profils[0] if profils else None

    # ── Création de profil ────────────────────────────────

    async def creer(
        self,
        data       : ProfilLocalCreateSchema,
        cree_par   : UUID,
        request_id : Optional[str] = None,
    ) -> ProfilResponseSchema:
        """
        Crée un nouveau profil rattaché à un CompteLocal existant.
        Permet l'inscription dans une nouvelle filière.
        """
        compte = await self.compte_repo.get_by_id(data.compte_id)
        if not compte:
            raise NotFoundError("CompteLocal", str(data.compte_id))
        if compte.statut not in ["actif", "bootstrap"]:
            raise ValidationError(
                f"Impossible de créer un profil pour un compte {compte.statut}."
            )

        profil = await self.repo.create({
            "compte_id"          : data.compte_id,
            "username"           : compte.username,
            "type_profil"        : data.type_profil.value if hasattr(data.type_profil, "value") else data.type_profil,
            "statut"             : "actif",
            "contexte_scolaire"  : data.contexte_scolaire or {},
            "meta_data"          : data.meta_data or {},
            "notes"              : data.notes,
            "created_by"         : cree_par,
        })

        await self.audit.log(
            type_action = "profil_cree",
            profil_id   = profil.id,
            module      = "iam",
            ressource   = "profil",
            action      = "creer",
            autorise    = True,
            raison      = f"Nouveau profil créé pour le compte {data.compte_id}",
            request_id  = request_id,
        )

        await self.producer.publish(
            topic   = Topics.IAM_PROFIL_CREE,
            payload = {
                "profil_id"   : str(profil.id),
                "compte_id"   : str(data.compte_id),
                "type_profil" : profil.type_profil,
            },
        )

        return self._to_response(profil, compte)

    async def creer_manuel(
        self,
        data       : ProfilLocalCreateSchema,
        cree_par   : UUID,
        request_id : Optional[str] = None,
    ) -> ProfilResponseSchema:
        """Alias de creer() — conservé pour compatibilité API bootstrap."""
        return await self.creer(data, cree_par, request_id)

    async def creer_avec_credentials(
        self,
        data       : ProfilLocalWithCredentialsCreateSchema,
        cree_par   : UUID,
        request_id : Optional[str] = None,
    ) -> ProfilResponseSchema:
        """
        Crée un compte local + profil en une seule opération,
        avec credentials pour authentification locale.
        Utilisé par le bootstrap et les admins créant des utilisateurs locaux.
        """
        # 1. Créer le CompteLocal avec credentials
        compte_data = CompteLocalAvecCredentialsCreateSchema(
            nom                     = data.nom,
            prenom                  = data.prenom,
            email                   = data.email,
            telephone               = data.telephone,
            identifiant_national    = data.identifiant_national,
            username                = data.username,
            password                = data.password,
            require_password_change = data.require_password_change,
            meta_data               = data.meta_data or {},
            notes                   = data.notes,
        )
        compte = await self.compte_svc.creer_avec_credentials(
            data       = compte_data,
            cree_par   = cree_par,
            request_id = request_id,
        )

        # 2. Construire le contexte scolaire depuis les champs académiques
        contexte_scolaire = {}
        if data.classe:
            contexte_scolaire["classe"] = data.classe
        if data.niveau:
            contexte_scolaire["niveau"] = data.niveau
        if data.specialite:
            contexte_scolaire["specialite"] = data.specialite
        if data.annee_scolaire:
            contexte_scolaire["annee_scolaire"] = data.annee_scolaire

        # 3. Créer le ProfilLocal rattaché au compte
        type_profil = data.type_profil.value if hasattr(data.type_profil, "value") else data.type_profil
        profil = await self.repo.create({
            "compte_id"          : compte.id,
            "username"           : data.username,
            "type_profil"        : type_profil,
            "statut"             : "actif",
            "contexte_scolaire"  : contexte_scolaire,
            "meta_data"          : data.meta_data or {},
            "notes"              : data.notes,
            "created_by"         : cree_par,
        })

        await self.audit.log(
            type_action = "profil_cree_avec_credentials",
            profil_id   = profil.id,
            module      = "iam",
            ressource   = "profil",
            action      = "creer",
            autorise    = True,
            raison      = f"Création avec credentials locales - Type: {type_profil}",
            request_id  = request_id,
        )

        await self.db.refresh(profil)
        return self._to_response(profil, compte)

    # ── Consultation ──────────────────────────────────────

    async def get_by_id(self, id: UUID) -> ProfilResponseSchema:
        profil = await self.repo.get_with_compte(id)
        if not profil:
            raise NotFoundError("Profil", str(id))
        return self._to_response(profil, profil.compte)

    async def get_by_user_id_national(
        self, user_id_national: UUID
    ) -> ProfilResponseSchema:
        profil = await self.repo.get_by_user_id_national(user_id_national)
        if not profil:
            raise NotFoundError("Profil", str(user_id_national))
        await self.db.refresh(profil, ["compte"])
        return self._to_response(profil, profil.compte)

    async def get_profils_du_compte(
        self, compte_id: UUID
    ) -> List[ProfilResponseSchema]:
        """Retourne tous les profils d'un compte (toutes les inscriptions)."""
        compte = await self.compte_repo.get_by_id(compte_id)
        if not compte:
            raise NotFoundError("CompteLocal", str(compte_id))
        profils = await self.repo.get_by_compte_id(compte_id)
        return [self._to_response(p, compte) for p in profils]

    async def get_all(
        self,
        skip        : int           = 0,
        limit       : int           = 50,
        type_profil : Optional[str] = None,
        statut      : Optional[str] = None,
        q           : Optional[str] = None,
    ) -> List[ProfilListSchema]:
        if q:
            items = await self.repo.search(q)
        elif type_profil:
            items = await self.repo.get_by_type(type_profil)
        elif statut:
            items = await self.repo.get_by_statut(statut)
        else:
            items = await self.repo.get_all(skip=skip, limit=limit)

        result = []
        for p in items:
            compte = await self.compte_repo.get_by_id(p.compte_id)
            result.append(self._to_list(p, compte))
        return result

    # ── Modification ──────────────────────────────────────

    async def update(
        self,
        id         : UUID,
        data       : ProfilLocalUpdateSchema,
        updated_by : UUID,
    ) -> ProfilResponseSchema:
        profil = await self.repo.get_with_compte(id)
        if not profil:
            raise NotFoundError("Profil", str(id))

        update_data = {
            k: v for k, v in data.model_dump().items() if v is not None
        }
        update_data["updated_by"] = updated_by
        profil = await self.repo.update(profil, update_data)
        return self._to_response(profil, profil.compte)

    async def suspendre(
        self,
        id         : UUID,
        data       : SuspendreProfilSchema,
        suspend_by : UUID,
        request_id : Optional[str] = None,
    ) -> ProfilResponseSchema:
        profil = await self.repo.get_with_compte(id)
        if not profil:
            raise NotFoundError("Profil", str(id))
        if profil.statut == "suspendu":
            raise ValidationError("Ce profil est déjà suspendu.")

        profil = await self.repo.update(profil, {
            "statut"           : "suspendu",
            "raison_suspension": data.raison,
            "updated_by"       : suspend_by,
        })

        await self.audit.log(
            type_action = "profil_suspendu",
            profil_id   = id,
            module      = "iam",
            ressource   = "profil",
            action      = "suspendre",
            autorise    = True,
            raison      = data.raison,
            request_id  = request_id,
        )

        await self.producer.publish(
            topic   = Topics.IAM_PROFIL_SUSPENDU,
            payload = {
                "profil_id"  : str(profil.id),
                "compte_id"  : str(profil.compte_id),
                "raison"     : data.raison,
                "suspend_by" : str(suspend_by),
            },
        )
        return self._to_response(profil, profil.compte)

    async def reactiver(
        self,
        id         : UUID,
        updated_by : UUID,
    ) -> ProfilResponseSchema:
        profil = await self.repo.get_with_compte(id)
        if not profil:
            raise NotFoundError("Profil", str(id))
        profil = await self.repo.update(profil, {
            "statut"           : "actif",
            "raison_suspension": None,
            "updated_by"       : updated_by,
        })
        return self._to_response(profil, profil.compte)

    async def supprimer(
        self,
        id         : UUID,
        deleted_by : UUID,
        request_id : Optional[str] = None,
    ) -> None:
        profil = await self.repo.get_by_id(id)
        if not profil:
            raise NotFoundError("Profil", str(id))
        if profil.username == "bootstrap":
            raise ValidationError(
                "Le profil bootstrap ne peut pas être supprimé directement."
            )

        await self.repo.soft_delete(profil, deleted_by)

        await self.audit.log(
            type_action = "profil_supprime",
            profil_id   = id,
            module      = "iam",
            ressource   = "profil",
            action      = "supprimer",
            autorise    = True,
            raison      = "Suppression par administrateur",
            request_id  = request_id,
        )

        await self.producer.publish(
            topic   = Topics.IAM_PROFIL_SUSPENDU,
            payload = {
                "profil_id"  : str(id),
                "raison"     : "supprimé",
                "deleted_by" : str(deleted_by),
            },
        )

    # ── Rôles / Assignations ──────────────────────────────

    async def assigner_role(
        self,
        data       : AssignationRoleCreateSchema,
        created_by : UUID,
        request_id : Optional[str] = None,
    ) -> AssignationRoleResponseSchema:
        profil = await self.repo.get_by_id(data.profil_id)
        if not profil:
            raise NotFoundError("Profil", str(data.profil_id))
        if profil.statut not in ["actif", "bootstrap"]:
            raise ValidationError(
                "Impossible d'assigner un rôle à un profil inactif."
            )

        from app.repositories.role import RoleRepository
        role_repo = RoleRepository(self.repo.db)
        role = await role_repo.get_by_id(data.role_id)
        if not role:
            raise NotFoundError("Rôle", str(data.role_id))

        if role.perimetre_obligatoire and not data.perimetre:
            raise ValidationError(
                f"Le rôle '{role.nom}' nécessite un périmètre explicite."
            )

        existante = await self.assign_repo.get_assignation_existante(
            data.profil_id, data.role_id
        )
        if existante:
            raise AlreadyExistsError(
                "Assignation", "profil+rôle",
                f"{data.profil_id}+{data.role_id}"
            )

        assignation = await self.assign_repo.create({
            **data.model_dump(),
            "statut"     : "active",
            "assigne_par": created_by,
            "created_by" : created_by,
        })

        await self.audit.log_assignation_role(
            profil_id  = data.profil_id,
            role_code  = role.code,
            assigne_par= created_by,
            perimetre  = data.perimetre,
            request_id = request_id,
        )

        await self.producer.publish(
            topic   = Topics.IAM_ROLE_ASSIGNE,
            payload = {
                "profil_id" : str(data.profil_id),
                "role_id"   : str(data.role_id),
                "role_code" : role.code,
                "perimetre" : data.perimetre,
            },
        )

        # Invalider le cache — le profil a un nouveau rôle
        from app.services.habilitation_service import HabilitationService
        hab_service = HabilitationService(self.repo.db)
        await hab_service.invalider_cache(data.profil_id)

        return AssignationRoleResponseSchema.model_validate(assignation)

    async def revoquer_role(
        self,
        assignation_id : UUID,
        revoque_par    : UUID,
        data           : RevoquerAssignationSchema,
        request_id     : Optional[str] = None,
    ) -> None:
        assignation = await self.assign_repo.revoquer(
            assignation_id,
            revoque_par,
            data.raison_revocation,
        )
        if not assignation:
            raise NotFoundError("Assignation", str(assignation_id))

        from app.repositories.role import RoleRepository
        role_repo = RoleRepository(self.repo.db)
        role = await role_repo.get_by_id(assignation.role_id)

        await self.audit.log_revocation_role(
            profil_id  = assignation.profil_id,
            role_code  = role.code if role else "inconnu",
            revoque_par= revoque_par,
            raison     = data.raison_revocation,
            request_id = request_id,
        )

        await self.producer.publish(
            topic   = Topics.IAM_ROLE_REVOQUE,
            payload = {
                "profil_id" : str(assignation.profil_id),
                "role_id"   : str(assignation.role_id),
                "raison"    : data.raison_revocation,
            },
        )

        # Invalider le cache — le profil a perdu un rôle
        from app.services.habilitation_service import HabilitationService
        hab_service = HabilitationService(self.repo.db)
        await hab_service.invalider_cache(assignation.profil_id)

    # ── Helpers internes ─────────────────────────────────

    def _to_response(self, profil, compte) -> ProfilResponseSchema:
        """Construit le ProfilResponseSchema avec identité dénormalisée."""
        return ProfilResponseSchema(
            id                          = profil.id,
            created_at                  = profil.created_at,
            updated_at                  = profil.updated_at,
            created_by                  = profil.created_by,
            updated_by                  = profil.updated_by,
            compte_id                   = profil.compte_id,
            username                    = profil.username,
            type_profil                 = profil.type_profil,
            statut                      = profil.statut,
            raison_suspension           = profil.raison_suspension,
            derniere_connexion          = profil.derniere_connexion,
            nb_connexions               = profil.nb_connexions,
            premiere_connexion          = profil.premiere_connexion,
            contexte_scolaire           = profil.contexte_scolaire or {},
            preferences                 = profil.preferences or {},
            meta_data                   = profil.meta_data or {},
            notes                       = profil.notes,
            # ── Identité dénormalisée depuis CompteLocal ──
            compte_nom                  = compte.nom if compte else None,
            compte_prenom               = compte.prenom if compte else None,
            compte_email                = compte.email if compte else None,
            compte_telephone            = compte.telephone if compte else None,
            compte_identifiant_national = compte.identifiant_national if compte else None,
            compte_user_id_national     = compte.user_id_national if compte else None,
            require_password_change     = compte.require_password_change if compte else None,
        )

    def _to_list(self, profil, compte) -> ProfilListSchema:
        return ProfilListSchema(
            id                          = profil.id,
            created_at                  = profil.created_at,
            updated_at                  = profil.updated_at,
            compte_id                   = profil.compte_id,
            username                    = profil.username,
            type_profil                 = profil.type_profil,
            statut                      = profil.statut,
            derniere_connexion          = profil.derniere_connexion,
            compte_nom                  = compte.nom if compte else None,
            compte_prenom               = compte.prenom if compte else None,
            compte_email                = compte.email if compte else None,
            compte_identifiant_national = compte.identifiant_national if compte else None,
        )
