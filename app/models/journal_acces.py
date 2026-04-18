from sqlalchemy import Column, String, Text, Boolean, DateTime, func
from sqlalchemy.dialects.postgresql import UUID, JSONB, INET
from sqlalchemy.orm import relationship
from app.database import Base
import uuid


class JournalAcces(Base):
    """
    Journal d'audit exhaustif de tous les accès et actions.
    Table NON soft-deletable — l'audit est immuable.
    Partitionnée par mois en production pour les performances.
    """
    __tablename__ = "journal_acces"

    id = Column(
        UUID(as_uuid=True),
        primary_key    = True,
        server_default = func.gen_random_uuid(),
    )

    # Horodatage
    timestamp = Column(
        DateTime(timezone=True),
        server_default = func.now(),
        nullable       = False,
        index          = True,
    )

    # Acteur
    profil_id        = Column(UUID(as_uuid=True), nullable=True, index=True)
    user_id_national = Column(UUID(as_uuid=True), nullable=True, index=True)
    nom_affiche      = Column(String(255), nullable=True)

    # Action
    # connexion | deconnexion | echec_auth |
    # acces_autorise | acces_refuse |
    # role_assigne | role_revoque | etc.
    type_action = Column(String(50), nullable=False, index=True)

    # Ressource accédée
    module      = Column(String(100), nullable=True)
    ressource   = Column(String(100), nullable=True)
    action      = Column(String(100), nullable=True)
    ressource_id = Column(String(255), nullable=True)

    # Permission vérifiée
    permission_verifiee = Column(String(200), nullable=True)
    perimetre_verifie   = Column(JSONB,       nullable=True)

    # Résultat
    autorise = Column(Boolean, nullable=True)
    raison   = Column(Text,    nullable=True)

    # Contexte technique
    ip_address  = Column(String(45),  nullable=True)
    user_agent  = Column(Text,        nullable=True)
    request_id  = Column(String(100), nullable=True, index=True)
    session_id  = Column(String(100), nullable=True)

    # Données supplémentaires
    details = Column(JSONB, nullable=True)
