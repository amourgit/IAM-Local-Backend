from typing import Optional, Any, List
from uuid import UUID
from pydantic import Field
from app.schemas.base import BaseSchema, BaseResponseSchema
from app.core.enums import TypeGroupe


class GroupeCreateSchema(BaseSchema):
    code        : str            = Field(..., min_length=1, max_length=100)
    nom         : str            = Field(..., min_length=2, max_length=255)
    description : Optional[str]  = None
    type_groupe : TypeGroupe      = TypeGroupe.FONCTIONNEL
    perimetre   : Optional[Any]   = None
    roles_ids   : Optional[List[UUID]] = []
    meta_data   : Optional[Any]   = {}
    notes       : Optional[str]   = None


class GroupeUpdateSchema(BaseSchema):
    nom         : Optional[str]       = None
    description : Optional[str]       = None
    type_groupe : Optional[TypeGroupe] = None
    perimetre   : Optional[Any]       = None
    actif       : Optional[bool]      = None
    meta_data   : Optional[Any]       = None
    notes       : Optional[str]       = None


class AjouterRolesGroupeSchema(BaseSchema):
    roles_ids  : List[UUID]
    perimetre  : Optional[Any] = None
    raison     : Optional[str] = None


class GroupeRoleSchema(BaseResponseSchema):
    groupe_id  : UUID
    role_id    : UUID
    perimetre  : Optional[Any] = None
    raison     : Optional[str] = None


class GroupeResponseSchema(BaseResponseSchema):
    code        : str
    nom         : str
    description : Optional[str] = None
    type_groupe : str
    perimetre   : Optional[Any] = None
    actif       : bool
    systeme     : bool
    meta_data   : Optional[Any] = {}
    notes       : Optional[str] = None
    nb_membres  : Optional[int] = 0


class GroupeListSchema(BaseResponseSchema):
    code        : str
    nom         : str
    type_groupe : str
    perimetre   : Optional[Any] = None
    actif       : bool
    nb_membres  : Optional[int] = 0
