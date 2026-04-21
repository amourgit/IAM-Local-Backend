"""Ajout colonne perimetre sur assignations_groupe

Revision ID: 0002_assignation_groupe_perimetre
Revises: 0001_initial_schema
Create Date: 2026-04-21
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = '0002_assignation_groupe_perimetre'
down_revision = '0001_initial_schema'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        'assignations_groupe',
        sa.Column(
            'perimetre',
            postgresql.JSONB(),
            nullable = True,
            comment  = "Périmètre spécifique à cette appartenance au groupe",
        ),
    )


def downgrade() -> None:
    op.drop_column('assignations_groupe', 'perimetre')
