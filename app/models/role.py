from sqlalchemy import Column, String, Text, Boolean, ForeignKey
from sqlalchemy.dialects.postgresql import UUID, JSONB
from sqlalchemy.orm import relationship
from app.models.base import BaseModel


# Table d'association Role ↔ Permission
from sqlalchemy import Table
from app.database import Base

role_permissions_table = Table(
    "role_permissions",
    Base.metadata,
    Column(
        "role_id",
        UUID(as_uuid=True),
        ForeignKey("roles.id", ondelete="CASCADE"),
        primary_key = True,
    ),
    Column(
        "permission_id",
        UUID(as_uuid=True),
        ForeignKey("permissions.id", ondelete="CASCADE"),
        primary_key = True,
    ),
)


class Role(BaseModel):
    """
    Regroupement nommé de permissions.
    Un rôle définit un profil fonctionnel réutilisable.
    ex: responsable_scolarite, chef_departement,
        gestionnaire_rh, directeur_composante
    """
    __tablename__ = "roles"

    # Identité
    code        = Column(String(100), nullable=False, unique=True, index=True)
    nom         = Column(String(255), nullable=False)
    description = Column(Text,        nullable=True)

    # Classification
    # fonctionnel | administratif | technique | temporaire | systeme
    type_role   = Column(
        String(50),
        nullable       = False,
        default        = "fonctionnel",
        server_default = "fonctionnel",
    )

    # Périmètre
    perimetre_obligatoire = Column(
        Boolean,
        nullable       = False,
        default        = False,
        server_default = "false",
        comment        = (
            "Si true, ce rôle doit être assigné "
            "avec un périmètre explicite"
        )
    )
    perimetre_schema = Column(
        JSONB,
        nullable = True,
        comment  = "Schéma des champs de périmètre attendus"
    )

    # Flags
    actif    = Column(Boolean, nullable=False, default=True)
    systeme  = Column(
        Boolean,
        nullable       = False,
        default        = False,
        server_default = "false",
        comment        = "Si true, rôle non modifiable par les admins"
    )

    meta_data = Column(JSONB, nullable=True, default=dict)
    notes     = Column(Text,  nullable=True)

    # Relations
    permissions = relationship(
        "Permission",
        secondary      = role_permissions_table,
        lazy           = "select",
    )
    assignations = relationship(
        "AssignationRole",
        back_populates = "role",
        lazy           = "select",
    )
    groupe_roles = relationship(
        "GroupeRole",
        back_populates = "role",
        lazy           = "select",
    )


class RolePermission(BaseModel):
    """
    Association explicite Role ↔ Permission
    avec métadonnées (date d'ajout, qui a ajouté).
    """
    __tablename__ = "role_permission_details"

    role_id = Column(
        UUID(as_uuid=True),
        ForeignKey("roles.id", ondelete="CASCADE"),
        nullable = False,
        index    = True,
    )
    permission_id = Column(
        UUID(as_uuid=True),
        ForeignKey("permissions.id", ondelete="CASCADE"),
        nullable = False,
        index    = True,
    )

    # Qui a ajouté cette permission au rôle
    ajoute_par = Column(UUID(as_uuid=True), nullable=True)
    raison     = Column(Text, nullable=True)

    # Relations
    role       = relationship("Role",       foreign_keys=[role_id])
    permission = relationship("Permission", back_populates="role_permissions")
