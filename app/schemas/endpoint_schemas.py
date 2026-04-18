from typing   import List, Optional
from datetime import datetime
from pydantic import BaseModel, Field, ConfigDict
from uuid     import UUID


class EndpointPermissionCreateSchema(BaseModel):
    module           : str           = Field(..., description="Nom du module (pour information)")
    path             : str           = Field(..., description="Chemin exact de l'endpoint")
    method           : str           = Field(..., description="Méthode HTTP (GET/POST/PUT/DELETE/PATCH)")
    permission_codes : List[str]     = Field(default=[], description="Codes des permissions requises")
    description      : Optional[str] = Field(None, description="Description de l'endpoint")


class EndpointPermissionResponseSchema(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id               : UUID
    source_id        : UUID
    path             : str
    method           : str
    permission_uuids : List[UUID]
    description      : Optional[str]
    public           : bool
    actif            : bool
    created_at       : datetime
    updated_at       : datetime


class EnregistrementEndpointsSchema(BaseModel):
    source_code : str                              = Field(..., description="Code de la source/microservice")
    module      : str                              = Field(..., description="Nom du module qui enregistre")
    version     : str                              = Field(..., description="Version du module")
    endpoints   : List[EndpointPermissionCreateSchema]


class EndpointPermissionDetailSchema(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id               : UUID
    source_id        : UUID
    source_code      : str
    source_nom       : str
    path             : str
    method           : str
    permission_uuids : List[UUID]
    permission_codes : List[str]
    description      : Optional[str]
    public           : bool
    actif            : bool
    created_at       : datetime
    updated_at       : datetime