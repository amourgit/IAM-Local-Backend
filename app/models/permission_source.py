from sqlalchemy import Column, String, Text, Boolean, Integer
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import relationship
from app.models.base import BaseModel


class PermissionSource(BaseModel):
    """
    Registre des microservices déclarant leurs permissions.
    Chaque microservice s'enregistre au démarrage avec
    la liste de ses permissions métier.
    IAM Local centralise et gère tout ici.
    """
    __tablename__ = "permission_sources"

    # Identité du microservice
    code        = Column(String(100), nullable=False, unique=True, index=True)
    nom         = Column(String(255), nullable=False)
    description = Column(Text,        nullable=True)
    version     = Column(String(50),  nullable=True)

    # URL de l'API du microservice (pour health check)
    url_base    = Column(String(500), nullable=True)

    # Statut
    actif       = Column(Boolean, nullable=False, default=True)

    # Métadonnées de synchronisation
    derniere_sync      = Column(String(50), nullable=True)
    nb_permissions     = Column(Integer,    nullable=False, default=0)

    # Infos complémentaires
    meta_data   = Column(JSONB, nullable=True, default=dict)
    notes       = Column(Text,  nullable=True)

    # Relations
    permissions = relationship(
        "Permission",
        back_populates = "source",
        lazy           = "select",
    )
