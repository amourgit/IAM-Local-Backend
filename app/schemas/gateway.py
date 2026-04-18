"""
Schémas pour le Gateway IAM Local.
Le frontend encapsule toutes ses requêtes vers les modules métier ici.
"""

from typing import Any, Dict, Optional
from pydantic import BaseModel, Field


class GatewayRequestSchema(BaseModel):
    """
    Requête encapsulée envoyée par le frontend vers IAM Local.
    IAM Local vérifie les permissions puis route vers le module cible.
    """
    module  : str = Field(..., description="Code du module cible ex: scolarite, notes, rh")
    path    : str = Field(..., description="Chemin de l'endpoint cible ex: /api/v1/inscriptions")
    method  : str = Field(..., description="Méthode HTTP: GET, POST, PUT, PATCH, DELETE")
    body    : Optional[Dict[str, Any]] = Field(None,  description="Corps de la requête")
    params  : Optional[Dict[str, Any]] = Field(None,  description="Query params")
    headers : Optional[Dict[str, str]] = Field(None,  description="Headers additionnels optionnels")


class GatewayResponseSchema(BaseModel):
    """
    Réponse retournée par le gateway au frontend.
    Encapsule la réponse du module métier.
    """
    success     : bool
    status_code : int
    data        : Optional[Any]         = None
    error       : Optional[str]         = None
    module      : str                   = ""
    path        : str                   = ""
    method      : str                   = ""


class ModuleConfig(BaseModel):
    """
    Configuration d'un module métier enregistré.
    """
    code        : str
    nom         : str
    base_url    : str
    actif       : bool = True
    description : Optional[str] = None
