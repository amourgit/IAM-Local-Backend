from typing import Optional, Any
from uuid import UUID
from pydantic import Field
from app.schemas.base import BaseSchema, BaseResponseSchema
from app.core.enums import NiveauRisque, DomainePermission


class PermissionSourceCreateSchema(BaseSchema):
    code        : str           = Field(..., min_length=1, max_length=100)
    nom         : str           = Field(..., min_length=2, max_length=255)
    description : Optional[str] = None
    version     : Optional[str] = None
    url_base    : Optional[str] = None
    meta_data   : Optional[Any] = {}
    notes       : Optional[str] = None


class PermissionSourceUpdateSchema(BaseSchema):
    nom         : Optional[str] = None
    description : Optional[str] = None
    version     : Optional[str] = None
    url_base    : Optional[str] = None
    actif       : Optional[bool] = None
    meta_data   : Optional[Any] = None
    notes       : Optional[str] = None


class PermissionSourceResponseSchema(BaseResponseSchema):
    code              : str
    nom               : str
    description       : Optional[str] = None
    version           : Optional[str] = None
    url_base          : Optional[str] = None
    actif             : bool
    derniere_sync     : Optional[str] = None
    nb_permissions    : int
    meta_data         : Optional[Any] = {}
    notes             : Optional[str] = None


# ── Permission ────────────────────────────────────────────

class PermissionCreateSchema(BaseSchema):
    source_id           : Optional[UUID] = None
    code                : str            = Field(..., min_length=1, max_length=200)
    nom                 : str            = Field(..., min_length=2, max_length=255)
    description         : Optional[str]  = None
    domaine             : str            = Field(..., max_length=100)
    ressource           : str            = Field(..., max_length=100)
    action              : str            = Field(..., max_length=100)
    niveau_risque       : NiveauRisque   = NiveauRisque.MOYEN
    necessite_perimetre : bool           = False
    exemple_perimetre   : Optional[Any]  = None
    meta_data           : Optional[Any]  = {}
    notes               : Optional[str]  = None


class PermissionUpdateSchema(BaseSchema):
    nom                 : Optional[str]          = None
    description         : Optional[str]          = None
    niveau_risque       : Optional[NiveauRisque] = None
    necessite_perimetre : Optional[bool]         = None
    actif               : Optional[bool]         = None
    deprecated          : Optional[bool]         = None
    exemple_perimetre   : Optional[Any]          = None
    meta_data           : Optional[Any]          = None
    notes               : Optional[str]          = None


class PermissionResponseSchema(BaseResponseSchema):
    source_id           : Optional[UUID] = None
    code                : str
    nom                 : str
    description         : Optional[str]  = None
    domaine             : str
    ressource           : str
    action              : str
    niveau_risque       : str
    actif               : bool
    necessite_perimetre : bool
    deprecated          : bool
    exemple_perimetre   : Optional[Any]  = None
    meta_data           : Optional[Any]  = {}
    notes               : Optional[str]  = None


class PermissionListSchema(BaseResponseSchema):
    code                : str
    nom                 : str
    domaine             : str
    ressource           : str
    action              : str
    niveau_risque       : str
    actif               : bool
    necessite_perimetre : bool
    deprecated          : bool


# ── Enregistrement en masse depuis un microservice ────────

class EnregistrementPermissionsSchema(BaseSchema):
    """
    Payload envoyé par un microservice pour déclarer
    ses permissions à IAM Local.
    """
    source_code    : str
    source_nom     : str
    source_version : str
    source_url     : Optional[str] = None
    permissions    : list[PermissionCreateSchema]


# ── Permissions custom administratives ─────────────────────

class PermissionCustomCreateSchema(BaseSchema):
    """Création d'une permission custom via l'UI IAM Local."""
    code          : str = Field(..., description="Code unique de la permission")
    nom           : str = Field(..., description="Libellé affichable")
    description   : Optional[str] = Field(None)
    domaine       : str = Field(...)
    ressource     : str = Field(...)
    action        : str = Field(...)
    niveau_risque : NiveauRisque = NiveauRisque.MOYEN
    necessite_perimetre : bool = False
    exemple_perimetre   : Optional[Any] = None
    meta_data           : Optional[Any] = {}
    notes               : Optional[str] = None

