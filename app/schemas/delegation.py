from typing import Optional, Any, List
from uuid import UUID
from datetime import datetime
from pydantic import Field
from app.schemas.base import BaseSchema, BaseResponseSchema


class DelegationCreateSchema(BaseSchema):
    delegataire_id          : UUID
    role_id                 : Optional[UUID]      = None
    permissions_specifiques : Optional[List[str]] = None
    perimetre               : Optional[Any]       = None
    date_debut              : datetime
    date_fin                : datetime
    motif                   : Optional[str]       = Field(None, min_length=10)

    class Config:
        json_schema_extra = {
            "example": {
                "delegataire_id": "uuid-adjoint",
                "role_id"       : "uuid-role-chef-dept",
                "date_debut"    : "2025-01-15T00:00:00Z",
                "date_fin"      : "2025-02-15T00:00:00Z",
                "motif"         : "Congé annuel du titulaire",
                "perimetre"     : {"departement_id": "uuid-dept"},
            }
        }


class RevoquerDelegationSchema(BaseSchema):
    raison_revocation : str = Field(..., min_length=5)


class DelegationResponseSchema(BaseResponseSchema):
    delegant_id             : UUID
    delegataire_id          : UUID
    role_id                 : Optional[UUID]      = None
    permissions_specifiques : Optional[List[str]] = None
    perimetre               : Optional[Any]       = None
    date_debut              : datetime
    date_fin                : datetime
    statut                  : str
    motif                   : Optional[str]       = None
    revoque_par             : Optional[UUID]      = None
    date_revocation         : Optional[datetime]  = None
    raison_revocation       : Optional[str]       = None
