from typing import Optional, Any, List
from uuid import UUID
from pydantic import Field
from app.schemas.base import BaseSchema


class PermissionEffective(BaseSchema):
    """Une permission effective avec son périmètre d'application."""
    id        : Optional[UUID] = None  # ✅ UUID pour comparaison middleware
    code      : str
    nom       : str
    domaine   : str
    ressource : str
    action    : str
    perimetre : Optional[Any] = None
    source    : str = "direct"


class HabilitationsSchema(BaseSchema):
    """
    Réponse complète des habilitations d'un profil.
    Calculée dynamiquement en combinant :
    - Rôles directs
    - Rôles via groupes
    - Délégations reçues actives
    """
    profil_id        : UUID
    user_id_national : Optional[UUID] = None  # ✅ Optional — None pour profils locaux sans IAM Central
    type_profil      : str
    statut           : str
    permissions      : List[PermissionEffective]
    roles_actifs     : List[str]
    groupes_actifs   : List[str]


class VerifierPermissionSchema(BaseSchema):
    """
    Payload pour vérifier si un profil a une permission
    sur un périmètre donné.
    Utilisé par tous les autres microservices.
    """
    permission : str  = Field(..., description="Code de permission ex: org.campus.modifier")
    perimetre  : Optional[Any] = Field(
        None,
        description="Périmètre à vérifier ex: {campus_id: uuid}"
    )


class ResultatVerificationSchema(BaseSchema):
    """Réponse à une vérification de permission."""
    autorise         : bool
    permission       : str
    perimetre        : Optional[Any]  = None
    raison           : Optional[str]  = None
    # Si autorisé — d'où vient la permission
    source           : Optional[str]  = None  # direct | role:code | groupe:code | delegation:uuid
    profil_id        : Optional[UUID] = None
    user_id_national : Optional[UUID] = None


class TokenSessionSchema(BaseSchema):
    """
    Token de session local généré après vérification
    du JWT IAM Central.
    Enrichi avec les habilitations locales.
    """
    access_token     : str
    token_type       : str = "bearer"
    expires_in       : int
    profil_id        : UUID
    user_id_national : Optional[UUID] = None  # ✅ Optional — None pour profils locaux sans IAM Central
    type_profil      : str
    permissions      : List[str]  # Liste des codes de permissions pour lookup rapide
