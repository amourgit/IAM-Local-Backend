from uuid import UUID
from typing import Optional, List
from sqlalchemy.ext.asyncio import AsyncSession
from app.repositories.role import RoleRepository
from app.repositories.permission import PermissionRepository
from app.schemas.role import (
    RoleCreateSchema,
    RoleUpdateSchema,
    AjouterPermissionsSchema,
    RetirerPermissionsSchema,
    RoleResponseSchema,
    RoleListSchema,
)
from app.core.exceptions import (
    NotFoundError,
    AlreadyExistsError,
    ValidationError,
    DependencyError,
)
from app.infrastructure.kafka.producer import KafkaProducer
from app.infrastructure.kafka.topics import Topics


class RoleService:

    def __init__(self, db: AsyncSession):
        self.repo      = RoleRepository(db)
        self.perm_repo = PermissionRepository(db)
        self.producer  = KafkaProducer()

    async def create(
        self,
        data       : RoleCreateSchema,
        created_by : UUID,
    ) -> RoleResponseSchema:

        if await self.repo.exists_by_code(data.code):
            raise AlreadyExistsError("Rôle", "code", data.code)

        permissions_ids = data.permissions_ids or []

        role = await self.repo.create({
            **data.model_dump(exclude={"permissions_ids"}),
            "created_by": created_by,
        })

        # Attacher les permissions si fournies
        if permissions_ids:
            await self._valider_permissions(permissions_ids)
            await self.repo.ajouter_permissions(
                role.id, permissions_ids, created_by
            )

        await self.producer.publish(
            topic   = Topics.IAM_ROLE_CREE,
            payload = {
                "role_id"   : str(role.id),
                "code"      : role.code,
                "type_role" : role.type_role,
            },
        )

        role = await self.repo.get_by_id_with_permissions(role.id)
        return RoleResponseSchema.model_validate(role)

    async def get_by_id(self, id: UUID) -> RoleResponseSchema:
        role = await self.repo.get_by_id_with_permissions(id)
        if not role:
            raise NotFoundError("Rôle", str(id))
        return RoleResponseSchema.model_validate(role)

    async def get_all(
        self,
        skip      : int           = 0,
        limit     : int           = 50,
        type_role : Optional[str] = None,
        q         : Optional[str] = None,
    ) -> List[RoleListSchema]:

        if q:
            items = await self.repo.search(q)
        elif type_role:
            items = await self.repo.get_by_type(type_role)
        else:
            items = await self.repo.get_actifs()

        # Calculer nb_permissions pour chaque rôle
        result = []
        for role in items:
            role_with_perms = await self.repo.get_by_id_with_permissions(
                role.id
            )
            schema = RoleListSchema.model_validate(role)
            schema.nb_permissions = len(role_with_perms.permissions or [])
            result.append(schema)

        return result

    async def update(
        self,
        id         : UUID,
        data       : RoleUpdateSchema,
        updated_by : UUID,
    ) -> RoleResponseSchema:

        role = await self.repo.get_by_id(id)
        if not role:
            raise NotFoundError("Rôle", str(id))

        if role.systeme:
            raise ValidationError(
                "Les rôles système ne peuvent pas être modifiés."
            )

        update_data = {
            k: v for k, v in data.model_dump().items()
            if v is not None
        }
        update_data["updated_by"] = updated_by
        role = await self.repo.update(role, update_data)

        await self.producer.publish(
            topic   = Topics.IAM_ROLE_MODIFIE,
            payload = {
                "role_id" : str(role.id),
                "changes" : {k: str(v) for k, v in update_data.items()},
            },
        )

        role = await self.repo.get_by_id_with_permissions(role.id)
        return RoleResponseSchema.model_validate(role)

    async def ajouter_permissions(
        self,
        role_id    : UUID,
        data       : AjouterPermissionsSchema,
        updated_by : UUID,
    ) -> RoleResponseSchema:

        role = await self.repo.get_by_id(role_id)
        if not role:
            raise NotFoundError("Rôle", str(role_id))

        if role.systeme:
            raise ValidationError(
                "Impossible de modifier les permissions d'un rôle système."
            )

        await self._valider_permissions(data.permissions_ids)
        await self.repo.ajouter_permissions(
            role_id, data.permissions_ids, updated_by, data.raison
        )

        # Invalider le cache de tous les profils ayant ce rôle
        await self._invalider_cache_role(role_id)

        role = await self.repo.get_by_id_with_permissions(role_id)
        return RoleResponseSchema.model_validate(role)

    async def retirer_permissions(
        self,
        role_id    : UUID,
        data       : RetirerPermissionsSchema,
        updated_by : UUID,
    ) -> RoleResponseSchema:

        role = await self.repo.get_by_id(role_id)
        if not role:
            raise NotFoundError("Rôle", str(role_id))

        if role.systeme:
            raise ValidationError(
                "Impossible de modifier les permissions d'un rôle système."
            )

        await self.repo.retirer_permissions(
            role_id, data.permissions_ids, updated_by
        )

        # Invalider le cache de tous les profils ayant ce rôle
        await self._invalider_cache_role(role_id)

        role = await self.repo.get_by_id_with_permissions(role_id)
        return RoleResponseSchema.model_validate(role)
        

    async def delete(self, id: UUID, deleted_by: UUID) -> None:
        role = await self.repo.get_by_id(id)
        if not role:
            raise NotFoundError("Rôle", str(id))

        if role.systeme:
            raise ValidationError(
                "Les rôles système ne peuvent pas être supprimés."
            )

        # Vérifier qu'aucune assignation active n'utilise ce rôle
        from app.repositories.assignation_role import AssignationRoleRepository
        assign_repo = AssignationRoleRepository(self.repo.db)
        assignations = await assign_repo.get_by_role(id)
        if assignations:
            raise DependencyError("Rôle", "assignations actives")

        await self.repo.soft_delete(role, deleted_by)

    async def _valider_permissions(
        self, permissions_ids: List[UUID]
    ) -> None:
        for perm_id in permissions_ids:
            perm = await self.perm_repo.get_by_id(perm_id)
            if not perm:
                raise NotFoundError("Permission", str(perm_id))
            if not perm.actif:
                raise ValidationError(
                    f"La permission {perm.code} est inactive."
                )
            if perm.deprecated:
                raise ValidationError(
                    f"La permission {perm.code} est dépréciée."
                )

    async def _invalider_cache_role(self, role_id: UUID) -> None:
        """Invalide le cache habilitations de tous les profils ayant ce rôle."""
        from app.repositories.assignation_role import AssignationRoleRepository
        from app.services.habilitation_service import HabilitationService
        assign_repo = AssignationRoleRepository(self.repo.db)
        assignations = await assign_repo.get_by_role(role_id)
        hab_service = HabilitationService(self.repo.db)
        for assignation in assignations:
            await hab_service.invalider_cache(assignation.profil_id)
