from typing import Optional, Any, List
from uuid import UUID
from datetime import datetime
from pydantic import Field
from app.schemas.base import BaseSchema, BaseResponseSchema


class AssignationRoleCreateSchema(BaseSchema):
    profil_id          : UUID
    role_id            : UUID
    perimetre          : Optional[Any]      = None
    date_debut         : Optional[datetime] = None
    date_fin           : Optional[datetime] = None
    raison_assignation : Optional[str]      = None


class AssignationRoleUpdateSchema(BaseSchema):
    perimetre          : Optional[Any]      = None
    date_fin           : Optional[datetime] = None
    statut             : Optional[str]      = None
    raison_assignation : Optional[str]      = None


class RevoquerAssignationSchema(BaseSchema):
    raison_revocation : str = Field(..., min_length=5)


class AssignationRoleResponseSchema(BaseResponseSchema):
    profil_id          : UUID
    role_id            : UUID
    perimetre          : Optional[Any]      = None
    statut             : str
    date_debut         : Optional[datetime] = None
    date_fin           : Optional[datetime] = None
    assigne_par        : Optional[UUID]     = None
    revoque_par        : Optional[UUID]     = None
    date_revocation    : Optional[datetime] = None
    raison_revocation  : Optional[str]      = None
    raison_assignation : Optional[str]      = None


# ── Assignation Groupe ────────────────────────────────────

class AssignationGroupeCreateSchema(BaseSchema):
    profil_id  : UUID
    groupe_id  : UUID
    date_debut : Optional[datetime] = None
    date_fin   : Optional[datetime] = None
    raison     : Optional[str]      = None


class AssignationGroupeResponseSchema(BaseResponseSchema):
    profil_id    : UUID
    groupe_id    : UUID
    statut       : str
    date_debut   : Optional[datetime] = None
    date_fin     : Optional[datetime] = None
    ajoute_par   : Optional[UUID]     = None
    retire_par   : Optional[UUID]     = None
    date_retrait : Optional[datetime] = None
    raison       : Optional[str]      = None
