"""
Schemas du système d'habilitations IAM Local.

Hiérarchie du calcul des permissions effectives :
    ProfilLocal
        ├── AssignationRole → Role → [Permission ...]
        ├── AssignationGroupe → Groupe → GroupeRole → Role → [Permission ...]
        └── Delegation → Role ou permissions_specifiques
"""
from typing import Optional, Any, List, Dict
from uuid import UUID
from pydantic import Field
from app.schemas.base import BaseSchema


class PermissionEffective(BaseSchema):
    """
    Une permission effective avec son périmètre d'application et sa source.

    La source est une chaîne traçant l'origine exacte de la permission :
    - "role:code"                      → assignation directe
    - "groupe:code→role:code"          → via appartenance à un groupe
    - "delegation:uuid"                → délégation reçue
    - Sources multiples : "role:A|groupe:B→role:C"  (union)
    """
    id        : Optional[UUID] = None   # UUID de la permission en DB
    code      : str                     # "iam.profil.consulter"
    nom       : str                     # "Consulter les profils"
    domaine   : str                     # "iam"
    ressource : str                     # "profil"
    action    : str                     # "consulter"
    perimetre : Optional[Any] = None    # {"composante_id": "uuid", ...}
    source    : str = "direct"          # Traçabilité multi-source


class HabilitationsSchema(BaseSchema):
    """
    Habilitations complètes calculées d'un profil.

    Combine toutes les sources :
    - Rôles directs (AssignationRole)
    - Rôles via groupes (AssignationGroupe → GroupeRole → Role)
    - Délégations reçues actives (Delegation)

    Mise en cache Redis 15 minutes.
    Invalidée immédiatement après toute mutation d'habilitation.
    """
    profil_id        : UUID
    user_id_national : Optional[UUID] = None
    type_profil      : str
    statut           : str
    permissions      : List[PermissionEffective]
    roles_actifs     : List[str]
    groupes_actifs   : List[str]


class VerifierPermissionSchema(BaseSchema):
    """
    Payload pour vérifier une permission depuis un microservice.

    permission : code de permission (ex: "scolarite.dossier.modifier")
    perimetre  : contexte de la vérification (ex: {"composante_id": "uuid"})

    Si perimetre est None → vérification globale (sans contrainte de périmètre).
    Si perimetre est fourni → la permission accordée doit couvrir ce périmètre.
    """
    permission : str = Field(
        ...,
        description="Code de permission — ex: scolarite.dossier.modifier",
        examples=["iam.profil.consulter", "scolarite.dossier.modifier"],
    )
    perimetre : Optional[Dict[str, Any]] = Field(
        None,
        description=(
            "Périmètre à vérifier. "
            "Ex: {composante_id: uuid, annee_academique: 2024-2025}. "
            "None = vérification globale."
        ),
    )


class ResultatVerificationSchema(BaseSchema):
    """
    Résultat d'une vérification de permission.

    autorise : True si le profil possède la permission sur le périmètre demandé
    source   : origine de la permission si autorisé
               "role:code" | "groupe:code→role:code" | "delegation:uuid"
    raison   : motif du refus si non autorisé
    """
    autorise         : bool
    permission       : str
    perimetre        : Optional[Any]  = None
    raison           : Optional[str]  = None
    source           : Optional[str]  = None
    profil_id        : Optional[UUID] = None
    user_id_national : Optional[UUID] = None


class VerifierPermissionsBatchSchema(BaseSchema):
    """
    Vérification de plusieurs permissions en un seul appel.
    Optimisé pour les microservices qui ont besoin de plusieurs checks.
    """
    permissions : List[str] = Field(
        ...,
        min_length=1,
        max_length=50,
        description="Liste de codes de permissions à vérifier",
    )
    perimetre : Optional[Dict[str, Any]] = Field(
        None,
        description="Périmètre commun pour toutes les vérifications",
    )
    mode : str = Field(
        "any",
        description=(
            "Mode de vérification : "
            "'any' = au moins une (OR), "
            "'all' = toutes (AND)"
        ),
    )


class ResultatBatchSchema(BaseSchema):
    """Résultat d'une vérification batch de permissions."""
    autorise          : bool
    mode              : str
    permissions_ok    : List[str]  # Permissions accordées
    permissions_ko    : List[str]  # Permissions refusées
    profil_id         : Optional[UUID] = None
    user_id_national  : Optional[UUID] = None


class TokenSessionSchema(BaseSchema):
    """Token de session local enrichi avec les habilitations."""
    access_token     : str
    token_type       : str = "bearer"
    expires_in       : int
    profil_id        : UUID
    user_id_national : Optional[UUID] = None
    type_profil      : str
    permissions      : List[str]   # Codes de permissions
    permission_ids   : List[str]   # UUIDs (pour le firewall)
    roles            : List[str]   # Codes de rôles
    groupes          : List[str]   # Codes de groupes
