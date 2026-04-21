from sqlalchemy import Column, String, Text, DateTime, ForeignKey
from sqlalchemy.dialects.postgresql import UUID, JSONB
from sqlalchemy.orm import relationship
from app.models.base import BaseModel


class AssignationGroupe(BaseModel):
    """
    Appartenance d'un profil à un groupe.
    Via ce lien, le profil hérite de tous les rôles du groupe.
    """
    __tablename__ = "assignations_groupe"

    # Qui
    profil_id = Column(
        UUID(as_uuid=True),
        ForeignKey("profils_locaux.id", ondelete="CASCADE"),
        nullable = False,
        index    = True,
    )

    # Dans quel groupe
    groupe_id = Column(
        UUID(as_uuid=True),
        ForeignKey("groupes.id", ondelete="CASCADE"),
        nullable = False,
        index    = True,
    )

    # Statut : active | suspendue | expiree | revoquee
    statut = Column(
        String(20),
        nullable       = False,
        default        = "active",
        server_default = "active",
    )

    # Temporalité
    date_debut = Column(DateTime(timezone=True), nullable=True)
    date_fin   = Column(DateTime(timezone=True), nullable=True)

    # Traçabilité
    ajoute_par  = Column(UUID(as_uuid=True), nullable=True)
    retire_par  = Column(UUID(as_uuid=True), nullable=True)
    date_retrait = Column(DateTime(timezone=True), nullable=True)
    raison      = Column(Text, nullable=True)

    # Périmètre de l'appartenance au groupe
    # Surcharge le périmètre global du groupe si défini
    perimetre = Column(
        JSONB,
        nullable = True,
        comment  = "Périmètre spécifique à cette appartenance au groupe"
    )

    meta_data = Column(JSONB, nullable=True, default=dict)

    # Relations
    profil  = relationship("ProfilLocal", back_populates="assignations_groupe")
    groupe  = relationship("Groupe",      back_populates="membres")
