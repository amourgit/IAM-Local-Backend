from uuid import UUID
from typing import Optional, List
from sqlalchemy.ext.asyncio import AsyncSession
from app.repositories.permission import (
    PermissionRepository,
    PermissionSourceRepository,
)
from app.schemas.permission import (
    PermissionCreateSchema,
    PermissionUpdateSchema,
    PermissionResponseSchema,
    PermissionListSchema,
    PermissionSourceCreateSchema,
    PermissionSourceResponseSchema,
    EnregistrementPermissionsSchema,
)
from app.core.exceptions import (
    NotFoundError,
    AlreadyExistsError,
    ValidationError,
)
from app.infrastructure.kafka.producer import KafkaProducer
from app.infrastructure.kafka.topics import Topics


class PermissionService:

    def __init__(self, db: AsyncSession):
        self.repo        = PermissionRepository(db)
        self.source_repo = PermissionSourceRepository(db)
        self.producer    = KafkaProducer()

    # ── Sources ───────────────────────────────────────────

    async def enregistrer_source(
        self,
        data       : PermissionSourceCreateSchema,
        created_by : UUID,
    ) -> PermissionSourceResponseSchema:

        existante = await self.source_repo.get_by_code(data.code)
        if existante:
            raise AlreadyExistsError("Source", "code", data.code)

        source = await self.source_repo.create({
            **data.model_dump(),
            "created_by": created_by,
        })
        return PermissionSourceResponseSchema.model_validate(source)

    async def get_sources(self) -> List[PermissionSourceResponseSchema]:
        sources = await self.source_repo.get_actifs()
        return [
            PermissionSourceResponseSchema.model_validate(s)
            for s in sources
        ]

    # ── Permissions ───────────────────────────────────────

    async def create(
        self,
        data       : PermissionCreateSchema,
        created_by : UUID,
    ) -> PermissionResponseSchema:

        # Vérifier unicité du code
        existante = await self.repo.get_by_code(data.code)
        if existante:
            raise AlreadyExistsError("Permission", "code", data.code)

        # Vérifier cohérence code = domaine.ressource.action
        parties = data.code.split(".")
        if len(parties) < 3:
            raise ValidationError(
                "Le code de permission doit suivre la convention "
                "domaine.ressource.action "
                f"(ex: org.campus.modifier). Reçu: {data.code}"
            )

        permission = await self.repo.create({
            **data.model_dump(),
            "created_by": created_by,
        })

        await self.producer.publish(
            topic   = Topics.IAM_PERMISSION_CREEE,
            payload = {
                "permission_id" : str(permission.id),
                "code"          : permission.code,
                "domaine"       : permission.domaine,
            },
        )

        return PermissionResponseSchema.model_validate(permission)

    async def get_by_id(
        self, id: UUID
    ) -> PermissionResponseSchema:
        permission = await self.repo.get_by_id(id)
        if not permission:
            raise NotFoundError("Permission", str(id))
        return PermissionResponseSchema.model_validate(permission)

    async def get_all(
        self,
        skip    : int           = 0,
        limit   : int           = 100,
        domaine : Optional[str] = None,
        q       : Optional[str] = None,
    ) -> List[PermissionListSchema]:

        if q:
            items = await self.repo.search(q)
        elif domaine:
            items = await self.repo.get_by_domaine(domaine)
        else:
            items = await self.repo.get_actives()

        return [PermissionListSchema.model_validate(p) for p in items]

    async def update(
        self,
        id         : UUID,
        data       : PermissionUpdateSchema,
        updated_by : UUID,
    ) -> PermissionResponseSchema:

        permission = await self.repo.get_by_id(id)
        if not permission:
            raise NotFoundError("Permission", str(id))

        if permission.deprecated:
            raise ValidationError(
                "Impossible de modifier une permission dépréciée."
            )

        update_data = {
            k: v for k, v in data.model_dump().items()
            if v is not None
        }
        update_data["updated_by"] = updated_by

        permission = await self.repo.update(permission, update_data)

        await self.producer.publish(
            topic   = Topics.IAM_PERMISSION_MODIFIEE,
            payload = {
                "permission_id" : str(permission.id),
                "code"          : permission.code,
                "changes"       : {k: str(v) for k, v in update_data.items()},
            },
        )

        return PermissionResponseSchema.model_validate(permission)

    async def enregistrement_masse(
        self,
        data       : EnregistrementPermissionsSchema,
        created_by : Optional[UUID] = None,
    ) -> dict:
        """
        Point d'entrée pour les microservices.
        Ils déclarent toutes leurs permissions en une seule requête.
        IAM Local crée ou met à jour chaque permission.
        """

        # Récupérer ou créer la source
        source = await self.source_repo.get_by_code(data.source_code)
        if not source:
            source = await self.source_repo.create({
                "code"        : data.source_code,
                "nom"         : data.source_nom,
                "version"     : data.source_version,
                "url_base"    : data.source_url,
                "created_by"  : created_by,
            })

        creees  = 0
        mises_a_jour = 0
        ignorees = 0

        for perm_data in data.permissions:
            existante = await self.repo.get_by_code(perm_data.code)

            if existante:
                # Mettre à jour si la version a changé
                await self.repo.update(existante, {
                    "nom"                 : perm_data.nom,
                    "description"         : perm_data.description,
                    "niveau_risque"       : perm_data.niveau_risque,
                    "necessite_perimetre" : perm_data.necessite_perimetre,
                    "updated_by"          : created_by,
                })
                mises_a_jour += 1
            else:
                await self.repo.create({
                    **perm_data.model_dump(),
                    "source_id"  : source.id,
                    "created_by" : created_by,
                })
                creees += 1

        # Mettre à jour le compteur de la source
        total = await self.repo.count(
            filters=[
                self.repo.model.source_id == source.id,
            ]
        )
        await self.source_repo.update(source, {
            "nb_permissions"  : total,
            "derniere_sync"   : str(
                __import__("datetime").datetime.utcnow()
            ),
            "updated_by"      : created_by,
        })

        return {
            "source"      : data.source_code,
            "creees"      : creees,
            "mises_a_jour": mises_a_jour,
            "ignorees"    : ignorees,
            "total"       : total,
        }

    async def delete(
        self,
        id : UUID,
    ) -> None:
        """Supprime une permission, mais pas si elle est proposée par un module."""
        permission = await self.repo.get_by_id(id)
        if not permission:
            raise NotFoundError("Permission", str(id))

        if permission.source_id is not None:
            raise ValidationError(
                "Impossible de supprimer une permission proposée par un module. "
                "Vous pouvez la désactiver ou la marquer comme dépréciée."
            )

        await self.repo.delete(permission)
