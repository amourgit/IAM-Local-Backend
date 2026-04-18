from typing import List, Optional
from uuid import UUID
from sqlalchemy.ext.asyncio import AsyncSession

from app.repositories.endpoint_permission import EndpointPermissionRepository
from app.schemas.endpoint_schemas import (
    EndpointPermissionCreateSchema,
    EndpointPermissionResponseSchema,
    EnregistrementEndpointsSchema,
)
from app.core.exceptions import (
    NotFoundError,
    ValidationError,
    AlreadyExistsError,
)


class EndpointPermissionService:

    def __init__(self, db: AsyncSession):
        self.repo = EndpointPermissionRepository(db)

    async def register_endpoints(
        self,
        data       : EnregistrementEndpointsSchema,
        created_by : Optional[UUID] = None,
    ) -> List[EndpointPermissionResponseSchema]:

        from app.repositories.permission import (
            PermissionSourceRepository,
            PermissionRepository,
        )

        src_repo  = PermissionSourceRepository(self.repo.db)
        perm_repo = PermissionRepository(self.repo.db)

        # Résoudre la source
        source = await src_repo.get_by_code(data.source_code)
        if not source:
            raise NotFoundError("PermissionSource", data.source_code)

        # Collecter tous les codes uniques à résoudre
        all_codes = list({
            code
            for ep in data.endpoints
            for code in ep.permission_codes
        })

        # Construire le map code → UUID une seule fois
        code_to_uuid = {}
        for code in all_codes:
            perm = await perm_repo.get_by_code(code)
            if not perm:
                raise NotFoundError("Permission", code)
            code_to_uuid[code] = perm.id

        # Construire les endpoints avec UUIDs résolus
        to_create = []
        for ep in data.endpoints:
            if not ep.path.startswith("/"):
                raise ValidationError(
                    f"Le chemin doit commencer par / : {ep.path}"
                )
            to_create.append({
                "path"            : ep.path,
                "method"          : ep.method.upper(),
                "permission_uuids": [code_to_uuid[c] for c in ep.permission_codes],
                "description"     : ep.description,
                "public"          : False,
                "actif"           : True,
            })

        await self.repo.replace_for_source(source.id, to_create)

        created = await self.repo.replace_for_source(source.id, to_create)
        return [
            EndpointPermissionResponseSchema.model_validate(e)
            for e in created
        ]

    async def list_by_source(
        self,
        source_id : UUID,
    ) -> List[EndpointPermissionResponseSchema]:

        items = await self.repo.get_by_source(source_id)
        return [
            EndpointPermissionResponseSchema.model_validate(e)
            for e in items
        ]

    async def get_for_request(
        self,
        source_id : UUID,
        path      : str,
        method    : str,
    ) -> EndpointPermissionResponseSchema | None:

        ep = await self.repo.get_by_path_method(
            source_id, path, method.upper()
        )
        if not ep:
            return None
        return EndpointPermissionResponseSchema.model_validate(ep)