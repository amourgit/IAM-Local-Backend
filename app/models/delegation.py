from sqlalchemy import Column, String, Text, DateTime, ForeignKey
from sqlalchemy.dialects.postgresql import UUID, JSONB
from sqlalchemy.orm import relationship
from app.models.base import BaseModel


class Delegation(BaseModel):
    """
    Transfert temporaire de droits entre deux profils.
    Utile pour les remplacements, congés, missions.
    ex: un chef de département délègue ses droits
    de validation à un adjoint pendant ses congés.
    """
    __tablename__ = "delegations"

    # Qui délègue
    delegant_id = Column(
        UUID(as_uuid=True),
        ForeignKey("profils_locaux.id", ondelete="CASCADE"),
        nullable = False,
        index    = True,
    )

    # À qui
    delegataire_id = Column(
        UUID(as_uuid=True),
        ForeignKey("profils_locaux.id", ondelete="CASCADE"),
        nullable = False,
        index    = True,
    )

    # Quels droits (rôle ou permissions spécifiques)
    role_id = Column(
        UUID(as_uuid=True),
        ForeignKey("roles.id", ondelete="RESTRICT"),
        nullable = True,
        comment  = "null = délégation de permissions spécifiques"
    )
    permissions_specifiques = Column(
        JSONB,
        nullable = True,
        comment  = "Liste de codes de permissions si pas de rôle"
    )

    # Périmètre de la délégation
    perimetre = Column(JSONB, nullable=True)

    # Temporalité — obligatoire pour une délégation
    date_debut = Column(DateTime(timezone=True), nullable=False)
    date_fin   = Column(DateTime(timezone=True), nullable=False)

    # Statut : active | expiree | revoquee
    statut = Column(
        String(20),
        nullable       = False,
        default        = "active",
        server_default = "active",
        index          = True,
    )

    # Contexte
    motif       = Column(Text, nullable=True)
    revoque_par = Column(UUID(as_uuid=True), nullable=True)
    date_revocation = Column(DateTime(timezone=True), nullable=True)
    raison_revocation = Column(Text, nullable=True)

    meta_data = Column(JSONB, nullable=True, default=dict)

    # Relations
    delegant    = relationship(
        "ProfilLocal",
        foreign_keys   = [delegant_id],
        back_populates = "delegations_accordees",
    )
    delegataire = relationship(
        "ProfilLocal",
        foreign_keys   = [delegataire_id],
        back_populates = "delegations_recues",
    )
    role = relationship("Role", foreign_keys=[role_id])
