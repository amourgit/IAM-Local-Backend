import uuid
from datetime import datetime
from sqlalchemy import Boolean, DateTime, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column
from app.database import Base


class BaseModel(Base):
    """
    Classe de base abstraite pour tous les modèles.
    UUID comme clé primaire, timestamps automatiques,
    soft delete, audit trail.
    """
    __abstract__ = True

    id : Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key  = True,
        server_default = func.gen_random_uuid(),
        index        = True,
    )

    created_at : Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default = func.now(),
        nullable       = False,
    )
    updated_at : Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default = func.now(),
        onupdate       = func.now(),
        nullable       = False,
    )

    created_by : Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        nullable = True,
    )
    updated_by : Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        nullable = True,
    )

    is_deleted : Mapped[bool] = mapped_column(
        Boolean,
        default        = False,
        server_default = "false",
        nullable       = False,
    )
    deleted_at : Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable = True,
    )
    deleted_by : Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        nullable = True,
    )
