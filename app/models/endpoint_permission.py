from sqlalchemy import Column, String, Text, Boolean, Index, ForeignKey
from sqlalchemy.dialects.postgresql import UUID, ARRAY
from sqlalchemy.orm import relationship
from app.models.base import BaseModel


class EndpointPermission(BaseModel):
    """
    Registre des endpoints d'un module et leurs permissions requises.

    Déclaré par chaque microservice au démarrage.
    Utilisé par le Gateway IAM Local pour vérifier les permissions
    avant de router vers le module.

    Convention :
    - path : chemin de l'endpoint (ex: /api/v1/inscriptions)
    - method : GET, POST, PUT, DELETE, PATCH
    - permission_uuids : liste des UUID de permissions requises (OR logic)
    """
    __tablename__ = "endpoint_permissions"

    # Module propriétaire
    source_id = Column(
        UUID(as_uuid=True),
        ForeignKey("permission_sources.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    # Identité de l'endpoint
    path = Column(String(500), nullable=False)
    method = Column(String(10), nullable=False)  # GET, POST, PUT, DELETE, PATCH

    # Permissions requises (UUIDs)
    # Logique OR : l'utilisateur doit avoir AU MOINS UNE de ces permissions
    permission_uuids = Column(
        ARRAY(UUID(as_uuid=True)),
        nullable=False,
        default=[],
        server_default="{}",
    )

    # Métadonnées
    description = Column(Text, nullable=True)
    
    # Flags
    public = Column(
        Boolean,
        nullable=False,
        default=False,
        server_default="false",
        comment="Si true, endpoint accessible sans authentification"
    )
    actif = Column(
        Boolean,
        nullable=False,
        default=True,
        server_default="true",
    )

    # Audit
    notes = Column(Text, nullable=True)

    # Relations
    source = relationship(
        "PermissionSource",
        lazy="select",
    )

    # Index pour recherche rapide
    __table_args__ = (
        Index("ix_endpoint_source_path_method", "source_id", "path", "method", unique=True),
        Index("ix_endpoint_source", "source_id"),
    )

