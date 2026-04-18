from sqlalchemy import Column, String, Text, Boolean, ForeignKey
from sqlalchemy.dialects.postgresql import UUID, JSONB
from sqlalchemy.orm import relationship
from app.models.base import BaseModel


class Permission(BaseModel):
    """
    Unité atomique de permission métier.
    Convention de nommage : domaine.ressource.action
    ex: scolarite.inscription.valider
        org.campus.modifier
        rh.salaire.consulter
        finance.budget.approuver

    Déclarées par les microservices, centralisées ici.
    """
    __tablename__ = "permissions"

    # Source — quel microservice a déclaré cette permission
    source_id = Column(
        UUID(as_uuid=True),
        ForeignKey("permission_sources.id", ondelete="RESTRICT"),
        nullable = True,   # null = permission native IAM Local
        index    = True,
    )

    # Identité
    code        = Column(String(200), nullable=False, unique=True, index=True)
    nom         = Column(String(255), nullable=False)
    description = Column(Text,        nullable=True)

    # Classification
    domaine    = Column(String(100), nullable=False, index=True)
    ressource  = Column(String(100), nullable=False)
    action     = Column(String(100), nullable=False)

    # Niveau de risque
    # faible | moyen | eleve | critique
    niveau_risque = Column(
        String(20),
        nullable       = False,
        default        = "moyen",
        server_default = "moyen",
    )

    # Flags
    actif               = Column(Boolean, nullable=False, default=True)
    necessite_perimetre = Column(
        Boolean,
        nullable       = False,
        default        = False,
        server_default = "false",
        comment        = "Si true, doit être assignée avec un périmètre"
    )
    deprecated = Column(Boolean, nullable=False, default=False)

    # Documentation
    exemple_perimetre = Column(
        JSONB,
        nullable = True,
        comment  = "Exemple de périmètre valide pour cette permission"
    )
    meta_data = Column(JSONB, nullable=True, default=dict)
    notes     = Column(Text,  nullable=True)

    # Relations
    source = relationship(
        "PermissionSource",
        back_populates = "permissions",
        lazy           = "select",
    )
    role_permissions = relationship(
        "RolePermission",
        back_populates = "permission",
        lazy           = "select",
    )
