from typing import Optional, Any, List
from uuid import UUID
from pydantic import Field
from app.schemas.base import BaseSchema, BaseResponseSchema
from app.core.enums import TypeRole
from app.schemas.permission import PermissionListSchema


class RoleCreateSchema(BaseSchema):
    code                  : str          = Field(..., min_length=1, max_length=100)
    nom                   : str          = Field(..., min_length=2, max_length=255)
    description           : Optional[str] = None
    type_role             : TypeRole      = TypeRole.FONCTIONNEL
    perimetre_obligatoire : bool          = False
    perimetre_schema      : Optional[Any] = None
    permissions_ids       : Optional[List[UUID]] = []
    meta_data             : Optional[Any] = {}
    notes                 : Optional[str] = None


class RoleUpdateSchema(BaseSchema):
    nom                   : Optional[str]      = None
    description           : Optional[str]      = None
    type_role             : Optional[TypeRole] = None
    perimetre_obligatoire : Optional[bool]     = None
    perimetre_schema      : Optional[Any]      = None
    actif                 : Optional[bool]     = None
    meta_data             : Optional[Any]      = None
    notes                 : Optional[str]      = None


class AjouterPermissionsSchema(BaseSchema):
    """Ajouter des permissions à un rôle existant."""
    permissions_ids : List[UUID]
    raison          : Optional[str] = None


class RetirerPermissionsSchema(BaseSchema):
    """Retirer des permissions d'un rôle."""
    permissions_ids : List[UUID]
    raison          : Optional[str] = None


class RoleResponseSchema(BaseResponseSchema):
    code                  : str
    nom                   : str
    description           : Optional[str] = None
    type_role             : str
    perimetre_obligatoire : bool
    perimetre_schema      : Optional[Any] = None
    actif                 : bool
    systeme               : bool
    meta_data             : Optional[Any] = {}
    notes                 : Optional[str] = None
    permissions           : Optional[List[PermissionListSchema]] = []


class RoleListSchema(BaseResponseSchema):
    code                  : str
    nom                   : str
    type_role             : str
    perimetre_obligatoire : bool
    actif                 : bool
    systeme               : bool
    nb_permissions        : Optional[int] = 0
