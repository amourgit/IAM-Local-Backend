from sqlalchemy import Column, String, Text, Boolean, DateTime, ForeignKey
from sqlalchemy.dialects.postgresql import UUID, JSONB
from sqlalchemy.orm import relationship
from app.models.base import BaseModel


class AssignationRole(BaseModel):
    """
    Assignation d'un rôle à un profil utilisateur.
    Peut être limitée dans le temps et dans le périmètre.

    C'est ici que se joue la granularité des habilitations :
    même rôle, périmètres différents = droits différents.
    """
    __tablename__ = "assignations_role"

    # Qui
    profil_id = Column(
        UUID(as_uuid=True),
        ForeignKey("profils_locaux.id", ondelete="CASCADE"),
        nullable = False,
        index    = True,
    )

    # Quoi
    role_id = Column(
        UUID(as_uuid=True),
        ForeignKey("roles.id", ondelete="RESTRICT"),
        nullable = False,
        index    = True,
    )

    # Sur quoi (périmètre)
    perimetre = Column(
        JSONB,
        nullable = True,
        comment  = (
            "Périmètre d'application du rôle. "
            "ex: {campus_id, composante_id, departement_id, "
            "filiere_id, annee_academique}"
        )
    )

    # Statut
    # active | suspendue | expiree | revoquee
    statut = Column(
        String(20),
        nullable       = False,
        default        = "active",
        server_default = "active",
        index          = True,
    )

    # Temporalité
    date_debut = Column(DateTime(timezone=True), nullable=True)
    date_fin   = Column(
        DateTime(timezone=True),
        nullable = True,
        comment  = "null = pas d'expiration"
    )

    # Traçabilité
    assigne_par = Column(UUID(as_uuid=True), nullable=True)
    revoque_par = Column(UUID(as_uuid=True), nullable=True)
    date_revocation = Column(DateTime(timezone=True), nullable=True)
    raison_revocation = Column(Text, nullable=True)
    raison_assignation = Column(Text, nullable=True)

    meta_data = Column(JSONB, nullable=True, default=dict)

    # Relations
    profil = relationship("ProfilLocal", back_populates="assignations_role")
    role   = relationship("Role",        back_populates="assignations")
