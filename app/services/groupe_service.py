from uuid import UUID
from typing import Optional, List
from sqlalchemy.ext.asyncio import AsyncSession
from app.repositories.groupe import GroupeRepository
from app.repositories.role import RoleRepository
from app.repositories.assignation_groupe import AssignationGroupeRepository
from app.schemas.groupe import (
    GroupeCreateSchema,
    GroupeUpdateSchema,
    AjouterRolesGroupeSchema,
    GroupeResponseSchema,
    GroupeListSchema,
)
from app.schemas.assignation import (
    AssignationGroupeCreateSchema,
    AssignationGroupeResponseSchema,
)
from app.core.exceptions import (
    NotFoundError,
    AlreadyExistsError,
    ValidationError,
    DependencyError,
)
from app.infrastructure.kafka.producer import KafkaProducer
from app.infrastructure.kafka.topics import Topics


class GroupeService:

    def __init__(self, db: AsyncSession):
        self.repo        = GroupeRepository(db)
        self.role_repo   = RoleRepository(db)
        self.assign_repo = AssignationGroupeRepository(db)
        self.producer    = KafkaProducer()

    async def create(
        self,
        data       : GroupeCreateSchema,
        created_by : UUID,
    ) -> GroupeResponseSchema:

        if await self.repo.exists_by_code(data.code):
            raise AlreadyExistsError("Groupe", "code", data.code)

        roles_ids = data.roles_ids or []

        groupe = await self.repo.create({
            **data.model_dump(exclude={"roles_ids"}),
            "created_by": created_by,
        })

        # Attacher les rôles si fournis
        for role_id in roles_ids:
            role = await self.role_repo.get_by_id(role_id)
            if not role:
                raise NotFoundError("Rôle", str(role_id))
            await self.repo.ajouter_role(
                groupe.id, role_id, None, created_by
            )

        await self.producer.publish(
            topic   = Topics.IAM_GROUPE_CREE,
            payload = {
                "groupe_id"  : str(groupe.id),
                "code"       : groupe.code,
                "type_groupe": groupe.type_groupe,
            },
        )

        groupe = await self.repo.get_by_id_with_roles(groupe.id)
        return GroupeResponseSchema.model_validate(groupe)

    async def get_by_id(self, id: UUID) -> GroupeResponseSchema:
        groupe = await self.repo.get_by_id_with_roles(id)
        if not groupe:
            raise NotFoundError("Groupe", str(id))
        return GroupeResponseSchema.model_validate(groupe)

    async def get_all(
        self,
        skip        : int           = 0,
        limit       : int           = 50,
        type_groupe : Optional[str] = None,
    ) -> List[GroupeListSchema]:

        if type_groupe:
            items = await self.repo.get_by_type(type_groupe)
        else:
            items = await self.repo.get_actifs()

        result = []
        for g in items:
            membres = await self.assign_repo.get_by_groupe(g.id)
            schema  = GroupeListSchema.model_validate(g)
            schema.nb_membres = len(membres)
            result.append(schema)

        return result

    async def update(
        self,
        id         : UUID,
        data       : GroupeUpdateSchema,
        updated_by : UUID,
    ) -> GroupeResponseSchema:

        groupe = await self.repo.get_by_id(id)
        if not groupe:
            raise NotFoundError("Groupe", str(id))

        if groupe.systeme:
            raise ValidationError(
                "Les groupes système ne peuvent pas être modifiés."
            )

        update_data = {
            k: v for k, v in data.model_dump().items()
            if v is not None
        }
        update_data["updated_by"] = updated_by
        groupe = await self.repo.update(groupe, update_data)

        groupe = await self.repo.get_by_id_with_roles(groupe.id)
        return GroupeResponseSchema.model_validate(groupe)

    async def ajouter_roles(
        self,
        groupe_id  : UUID,
        data       : AjouterRolesGroupeSchema,
        updated_by : UUID,
    ) -> GroupeResponseSchema:

        groupe = await self.repo.get_by_id(groupe_id)
        if not groupe:
            raise NotFoundError("Groupe", str(groupe_id))

        for role_id in data.roles_ids:
            role = await self.role_repo.get_by_id(role_id)
            if not role:
                raise NotFoundError("Rôle", str(role_id))
            await self.repo.ajouter_role(
                groupe_id, role_id, data.perimetre, updated_by, data.raison
            )

        # Invalider le cache de tous les membres du groupe
        from app.services.habilitation_service import HabilitationService
        hab_service = HabilitationService(self.repo.db)
        await hab_service.invalider_cache_groupe(groupe_id)

        groupe = await self.repo.get_by_id_with_roles(groupe_id)
        return GroupeResponseSchema.model_validate(groupe)

    async def retirer_role(
        self,
        groupe_id  : UUID,
        role_id    : UUID,
        updated_by : UUID,
    ) -> GroupeResponseSchema:

        groupe = await self.repo.get_by_id(groupe_id)
        if not groupe:
            raise NotFoundError("Groupe", str(groupe_id))

        await self.repo.retirer_role(groupe_id, role_id, updated_by)

        # Invalider le cache de tous les membres du groupe
        from app.services.habilitation_service import HabilitationService
        hab_service = HabilitationService(self.repo.db)
        await hab_service.invalider_cache_groupe(groupe_id)

        groupe = await self.repo.get_by_id_with_roles(groupe_id)
        return GroupeResponseSchema.model_validate(groupe)

    async def ajouter_membre(
        self,
        data       : AssignationGroupeCreateSchema,
        created_by : UUID,
    ) -> AssignationGroupeResponseSchema:

        groupe = await self.repo.get_by_id(data.groupe_id)
        if not groupe:
            raise NotFoundError("Groupe", str(data.groupe_id))

        existante = await self.assign_repo.get_assignation_existante(
            data.profil_id, data.groupe_id
        )
        if existante:
            raise AlreadyExistsError(
                "Membre", "profil dans groupe", str(data.profil_id)
            )

        assignation = await self.assign_repo.create({
            **data.model_dump(),
            "statut"     : "active",
            "ajoute_par" : created_by,
            "created_by" : created_by,
        })

        await self.producer.publish(
            topic   = Topics.IAM_GROUPE_MEMBRE_AJOUTE,
            payload = {
                "groupe_id" : str(data.groupe_id),
                "profil_id" : str(data.profil_id),
            },
        )

        # Invalider le cache du nouveau membre — il hérite des rôles du groupe
        from app.services.habilitation_service import HabilitationService
        hab_service = HabilitationService(self.repo.db)
        await hab_service.invalider_cache(data.profil_id)

        return AssignationGroupeResponseSchema.model_validate(assignation)

    async def retirer_membre(
        self,
        assignation_id : UUID,
        retire_par     : UUID,
        raison         : Optional[str] = None,
    ) -> None:
        assignation = await self.assign_repo.retirer(
            assignation_id, retire_par, raison
        )
        if not assignation:
            raise NotFoundError("Assignation groupe", str(assignation_id))

        # Invalider le cache du membre retiré — il perd les rôles du groupe
        from app.services.habilitation_service import HabilitationService
        hab_service = HabilitationService(self.assign_repo.db)
        await hab_service.invalider_cache(assignation.profil_id)

    async def delete(self, id: UUID, deleted_by: UUID) -> None:
        groupe = await self.repo.get_by_id(id)
        if not groupe:
            raise NotFoundError("Groupe", str(id))

        if groupe.systeme:
            raise ValidationError(
                "Les groupes système ne peuvent pas être supprimés."
            )

        membres = await self.assign_repo.get_by_groupe(id)
        if membres:
            raise DependencyError("Groupe", "membres actifs")

        await self.repo.soft_delete(groupe, deleted_by)
