from typing import Optional, Any
from uuid import UUID
from datetime import datetime
from pydantic import Field
from app.schemas.base import BaseSchema, BaseResponseSchema


class JournalAccesResponseSchema(BaseSchema):
    id               : UUID
    timestamp        : datetime
    profil_id        : Optional[UUID] = None
    user_id_national : Optional[UUID] = None
    nom_affiche      : Optional[str]  = None
    type_action      : str
    module           : Optional[str]  = None
    ressource        : Optional[str]  = None
    action           : Optional[str]  = None
    ressource_id     : Optional[str]  = None
    permission_verifiee : Optional[str] = None
    perimetre_verifie   : Optional[Any] = None
    autorise         : Optional[bool] = None
    raison           : Optional[str]  = None
    ip_address       : Optional[str]  = None
    request_id       : Optional[str]  = None
    details          : Optional[Any]  = None


class FiltresJournalSchema(BaseSchema):
    """Filtres pour la recherche dans le journal."""
    profil_id        : Optional[UUID]     = None
    user_id_national : Optional[UUID]     = None
    type_action      : Optional[str]      = None
    module           : Optional[str]      = None
    autorise         : Optional[bool]     = None
    date_debut       : Optional[datetime] = None
    date_fin         : Optional[datetime] = None
    ip_address       : Optional[str]      = None
    skip             : int                = Field(0,  ge=0)
    limit            : int                = Field(50, ge=1, le=500)
