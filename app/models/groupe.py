from sqlalchemy import Column, String, Text, Boolean, ForeignKey
from sqlalchemy.dialects.postgresql import UUID, JSONB
from sqlalchemy.orm import relationship
from app.models.base import BaseModel


class Groupe(BaseModel):
    """
    Regroupement d'utilisateurs partageant les mêmes rôles.
    Simplifie la gestion en masse des habilitations.
    ex: chefs_departement_fst, jury_licence_info,
        gestionnaires_budgetaires, commission_pedagogique
    """
    __tablename__ = "groupes"

    # Identité
    code        = Column(String(100), nullable=False, unique=True, index=True)
    nom         = Column(String(255), nullable=False)
    description = Column(Text,        nullable=True)

    # Classification
    # fonctionnel | organisationnel | projet | technique
    type_groupe = Column(
        String(50),
        nullable       = False,
        default        = "fonctionnel",
        server_default = "fonctionnel",
    )

    # Périmètre du groupe — s'applique à tous ses membres
    perimetre = Column(
        JSONB,
        nullable = True,
        comment  = (
            "Périmètre commun à tous les membres du groupe. "
            "ex: {composante_id: uuid, annee_academique: 2024-2025}"
        )
    )

    # Flags
    actif   = Column(Boolean, nullable=False, default=True)
    systeme = Column(
        Boolean,
        nullable       = False,
        default        = False,
        server_default = "false",
    )

    meta_data = Column(JSONB, nullable=True, default=dict)
    notes     = Column(Text,  nullable=True)

    # Relations
    membres = relationship(
        "AssignationGroupe",
        back_populates = "groupe",
        lazy           = "select",
    )
    roles = relationship(
        "GroupeRole",
        back_populates = "groupe",
        lazy           = "select",
    )


class GroupeRole(BaseModel):
    """
    Association Groupe ↔ Role avec périmètre optionnel.
    Le périmètre ici surcharge celui du groupe si défini.
    """
    __tablename__ = "groupe_roles"

    groupe_id = Column(
        UUID(as_uuid=True),
        ForeignKey("groupes.id", ondelete="CASCADE"),
        nullable = False,
        index    = True,
    )
    role_id = Column(
        UUID(as_uuid=True),
        ForeignKey("roles.id", ondelete="CASCADE"),
        nullable = False,
        index    = True,
    )

    # Périmètre spécifique à cette association groupe-rôle
    perimetre  = Column(JSONB, nullable=True)
    ajoute_par = Column(UUID(as_uuid=True), nullable=True)
    raison     = Column(Text, nullable=True)

    # Relations
    groupe = relationship("Groupe", back_populates="roles")
    role   = relationship("Role",   back_populates="groupe_roles")
