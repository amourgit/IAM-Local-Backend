"""Initial schema complet — CompteLocal + ProfilLocal + seeds

Revision ID: 0001_initial_schema
Revises:
Create Date: 2026-04-18
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql
import uuid
from datetime import datetime, timezone

revision = '0001_initial_schema'
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    # ── 0. Reset et nettoyage propre ─────────────────────────────
    op.execute(sa.text("SET session_replication_role = replica"))
    for tbl in [
        'token_manager','token_settings',
        'endpoint_permissions','journal_acces','delegations',
        'assignations_groupe','assignations_role',
        'profils_locaux','comptes_locaux',
        'groupe_roles','groupes',
        'role_permission_details','role_permissions',
        'roles','permissions','permission_sources',
    ]:
        conn.execute(sa.text(f'DROP TABLE IF EXISTS "{tbl}" CASCADE'))
    op.execute(sa.text("SET session_replication_role = DEFAULT"))

    # ── 1. permission_sources ─────────────────────────────────────
    op.create_table('permission_sources',
        sa.Column('id', postgresql.UUID(as_uuid=True), server_default=sa.text('gen_random_uuid()'), primary_key=True, index=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('created_by', postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column('updated_by', postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column('is_deleted', sa.Boolean(), server_default='false', nullable=False),
        sa.Column('deleted_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('deleted_by', postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column('code',          sa.String(100),  nullable=False, unique=True, index=True),
        sa.Column('nom',           sa.String(255),  nullable=False),
        sa.Column('description',   sa.Text(),       nullable=True),
        sa.Column('version',       sa.String(50),   nullable=True),
        sa.Column('url_base',      sa.String(500),  nullable=True),
        sa.Column('actif',         sa.Boolean(),    server_default='true', nullable=False),
        sa.Column('derniere_sync', sa.String(50),   nullable=True),
        sa.Column('nb_permissions',sa.Integer(),    server_default='0', nullable=False),
        sa.Column('meta_data',     postgresql.JSONB(), nullable=True),
        sa.Column('notes',         sa.Text(),       nullable=True),
    )

    # ── 2. permissions ────────────────────────────────────────────
    op.create_table('permissions',
        sa.Column('id', postgresql.UUID(as_uuid=True), server_default=sa.text('gen_random_uuid()'), primary_key=True, index=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('created_by', postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column('updated_by', postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column('is_deleted', sa.Boolean(), server_default='false', nullable=False),
        sa.Column('deleted_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('deleted_by', postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column('source_id', postgresql.UUID(as_uuid=True),
                  sa.ForeignKey('permission_sources.id', ondelete='RESTRICT'), nullable=True, index=True),
        sa.Column('code',                sa.String(200), nullable=False, unique=True, index=True),
        sa.Column('nom',                 sa.String(255), nullable=False),
        sa.Column('description',         sa.Text(),      nullable=True),
        sa.Column('domaine',             sa.String(100), nullable=False, index=True),
        sa.Column('ressource',           sa.String(100), nullable=False),
        sa.Column('action',              sa.String(100), nullable=False),
        sa.Column('niveau_risque',       sa.String(20),  server_default='moyen', nullable=False),
        sa.Column('actif',               sa.Boolean(),   server_default='true',  nullable=False),
        sa.Column('necessite_perimetre', sa.Boolean(),   server_default='false', nullable=False),
        sa.Column('deprecated',          sa.Boolean(),   server_default='false', nullable=False),
        sa.Column('exemple_perimetre',   postgresql.JSONB(), nullable=True),
        sa.Column('meta_data',           postgresql.JSONB(), nullable=True),
        sa.Column('notes',               sa.Text(),      nullable=True),
    )

    # ── 3. roles ──────────────────────────────────────────────────
    op.create_table('roles',
        sa.Column('id', postgresql.UUID(as_uuid=True), server_default=sa.text('gen_random_uuid()'), primary_key=True, index=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('created_by', postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column('updated_by', postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column('is_deleted', sa.Boolean(), server_default='false', nullable=False),
        sa.Column('deleted_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('deleted_by', postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column('code',                 sa.String(100), nullable=False, unique=True, index=True),
        sa.Column('nom',                  sa.String(255), nullable=False),
        sa.Column('description',          sa.Text(),      nullable=True),
        sa.Column('type_role',            sa.String(50),  server_default='fonctionnel', nullable=False),
        sa.Column('perimetre_obligatoire',sa.Boolean(),   server_default='false', nullable=False),
        sa.Column('perimetre_schema',     postgresql.JSONB(), nullable=True),
        sa.Column('actif',                sa.Boolean(),   server_default='true',  nullable=False),
        sa.Column('systeme',              sa.Boolean(),   server_default='false', nullable=False),
        sa.Column('meta_data',            postgresql.JSONB(), nullable=True),
        sa.Column('notes',                sa.Text(),      nullable=True),
    )

    # ── 4. role_permissions (table d'asso simple via SQLAlchemy Table) ─
    op.create_table('role_permissions',
        sa.Column('role_id',       postgresql.UUID(as_uuid=True),
                  sa.ForeignKey('roles.id',       ondelete='CASCADE'), primary_key=True),
        sa.Column('permission_id', postgresql.UUID(as_uuid=True),
                  sa.ForeignKey('permissions.id', ondelete='CASCADE'), primary_key=True),
    )

    # ── 5. role_permission_details (RolePermission avec métadonnées) ─
    op.create_table('role_permission_details',
        sa.Column('id', postgresql.UUID(as_uuid=True), server_default=sa.text('gen_random_uuid()'), primary_key=True, index=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('created_by', postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column('updated_by', postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column('is_deleted', sa.Boolean(), server_default='false', nullable=False),
        sa.Column('deleted_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('deleted_by', postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column('role_id',       postgresql.UUID(as_uuid=True),
                  sa.ForeignKey('roles.id',       ondelete='CASCADE'), nullable=False, index=True),
        sa.Column('permission_id', postgresql.UUID(as_uuid=True),
                  sa.ForeignKey('permissions.id', ondelete='CASCADE'), nullable=False, index=True),
        sa.Column('ajoute_par', postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column('raison',     sa.Text(), nullable=True),
    )

    # ── 6. groupes ────────────────────────────────────────────────
    op.create_table('groupes',
        sa.Column('id', postgresql.UUID(as_uuid=True), server_default=sa.text('gen_random_uuid()'), primary_key=True, index=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('created_by', postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column('updated_by', postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column('is_deleted', sa.Boolean(), server_default='false', nullable=False),
        sa.Column('deleted_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('deleted_by', postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column('code',        sa.String(100), nullable=False, unique=True, index=True),
        sa.Column('nom',         sa.String(255), nullable=False),
        sa.Column('description', sa.Text(),      nullable=True),
        sa.Column('type_groupe', sa.String(50),  server_default='fonctionnel', nullable=False),
        sa.Column('perimetre',   postgresql.JSONB(), nullable=True),
        sa.Column('actif',       sa.Boolean(),   server_default='true',  nullable=False),
        sa.Column('systeme',     sa.Boolean(),   server_default='false', nullable=False),
        sa.Column('meta_data',   postgresql.JSONB(), nullable=True),
        sa.Column('notes',       sa.Text(),      nullable=True),
    )

    # ── 7. groupe_roles ───────────────────────────────────────────
    op.create_table('groupe_roles',
        sa.Column('id', postgresql.UUID(as_uuid=True), server_default=sa.text('gen_random_uuid()'), primary_key=True, index=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('created_by', postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column('updated_by', postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column('is_deleted', sa.Boolean(), server_default='false', nullable=False),
        sa.Column('deleted_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('deleted_by', postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column('groupe_id', postgresql.UUID(as_uuid=True),
                  sa.ForeignKey('groupes.id', ondelete='CASCADE'), nullable=False, index=True),
        sa.Column('role_id', postgresql.UUID(as_uuid=True),
                  sa.ForeignKey('roles.id',   ondelete='CASCADE'), nullable=False, index=True),
        sa.Column('perimetre',  postgresql.JSONB(), nullable=True),
        sa.Column('ajoute_par', postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column('raison',     sa.Text(), nullable=True),
    )

    # ── 8. comptes_locaux ─────────────────────────────────────────
    op.create_table('comptes_locaux',
        sa.Column('id', postgresql.UUID(as_uuid=True), server_default=sa.text('gen_random_uuid()'), primary_key=True, index=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('created_by', postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column('updated_by', postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column('is_deleted', sa.Boolean(), server_default='false', nullable=False),
        sa.Column('deleted_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('deleted_by', postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column('user_id_national',    postgresql.UUID(as_uuid=True), nullable=True, unique=True, index=True),
        sa.Column('nom',                 sa.String(255), nullable=True),
        sa.Column('prenom',              sa.String(255), nullable=True),
        sa.Column('email',               sa.String(255), nullable=True, index=True),
        sa.Column('telephone',           sa.String(50),  nullable=True),
        sa.Column('identifiant_national',sa.String(100), nullable=True, index=True),
        sa.Column('username',            sa.String(150), nullable=True, unique=True, index=True),
        sa.Column('statut',              sa.String(20),  server_default='actif', nullable=False, index=True),
        sa.Column('raison_suspension',   sa.Text(),      nullable=True),
        sa.Column('derniere_connexion',  sa.DateTime(timezone=True), nullable=True),
        sa.Column('nb_connexions',       sa.String(20),  server_default='0', nullable=True),
        sa.Column('premiere_connexion',  sa.DateTime(timezone=True), nullable=True),
        sa.Column('password_hash',       sa.String(255), nullable=True),
        sa.Column('password_salt',       sa.String(255), nullable=True),
        sa.Column('password_algorithm',  sa.String(50),  server_default='bcrypt', nullable=True),
        sa.Column('password_changed_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('failed_login_attempts',sa.Integer(),  server_default='0', nullable=False),
        sa.Column('locked_until',        sa.DateTime(timezone=True), nullable=True),
        sa.Column('require_password_change', sa.Boolean(), server_default='false', nullable=False),
        sa.Column('snapshot_iam_central',postgresql.JSONB(), nullable=True),
        sa.Column('preferences',         postgresql.JSONB(), nullable=True),
        sa.Column('meta_data',           postgresql.JSONB(), nullable=True),
        sa.Column('notes',               sa.Text(), nullable=True),
    )

    # ── 9. profils_locaux ─────────────────────────────────────────
    op.create_table('profils_locaux',
        sa.Column('id', postgresql.UUID(as_uuid=True), server_default=sa.text('gen_random_uuid()'), primary_key=True, index=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('created_by', postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column('updated_by', postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column('is_deleted', sa.Boolean(), server_default='false', nullable=False),
        sa.Column('deleted_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('deleted_by', postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column('compte_id', postgresql.UUID(as_uuid=True),
                  sa.ForeignKey('comptes_locaux.id', ondelete='CASCADE'), nullable=False, index=True),
        sa.Column('username',            sa.String(150), nullable=True, unique=True, index=True),
        sa.Column('type_profil',         sa.String(50),  server_default='invite', nullable=False, index=True),
        sa.Column('statut',              sa.String(20),  server_default='actif',  nullable=False, index=True),
        sa.Column('raison_suspension',   sa.Text(),      nullable=True),
        sa.Column('derniere_connexion',  sa.DateTime(timezone=True), nullable=True),
        sa.Column('nb_connexions',       sa.String(20),  server_default='0', nullable=True),
        sa.Column('premiere_connexion',  sa.DateTime(timezone=True), nullable=True),
        sa.Column('contexte_scolaire',   postgresql.JSONB(), nullable=True),
        sa.Column('preferences',         postgresql.JSONB(), nullable=True),
        sa.Column('meta_data',           postgresql.JSONB(), nullable=True),
        sa.Column('notes',               sa.Text(), nullable=True),
    )

    # ── 10. assignations_role ─────────────────────────────────────
    op.create_table('assignations_role',
        sa.Column('id', postgresql.UUID(as_uuid=True), server_default=sa.text('gen_random_uuid()'), primary_key=True, index=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('created_by', postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column('updated_by', postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column('is_deleted', sa.Boolean(), server_default='false', nullable=False),
        sa.Column('deleted_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('deleted_by', postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column('profil_id', postgresql.UUID(as_uuid=True),
                  sa.ForeignKey('profils_locaux.id', ondelete='CASCADE'), nullable=False, index=True),
        sa.Column('role_id', postgresql.UUID(as_uuid=True),
                  sa.ForeignKey('roles.id', ondelete='RESTRICT'), nullable=False, index=True),
        sa.Column('perimetre',          postgresql.JSONB(), nullable=True),
        sa.Column('statut',             sa.String(20),  server_default='active', nullable=False, index=True),
        sa.Column('date_debut',         sa.DateTime(timezone=True), nullable=True),
        sa.Column('date_fin',           sa.DateTime(timezone=True), nullable=True),
        sa.Column('assigne_par',        postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column('revoque_par',        postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column('date_revocation',    sa.DateTime(timezone=True), nullable=True),
        sa.Column('raison_revocation',  sa.Text(), nullable=True),
        sa.Column('raison_assignation', sa.Text(), nullable=True),
        sa.Column('meta_data',          postgresql.JSONB(), nullable=True),
    )

    # ── 11. assignations_groupe ───────────────────────────────────
    op.create_table('assignations_groupe',
        sa.Column('id', postgresql.UUID(as_uuid=True), server_default=sa.text('gen_random_uuid()'), primary_key=True, index=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('created_by', postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column('updated_by', postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column('is_deleted', sa.Boolean(), server_default='false', nullable=False),
        sa.Column('deleted_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('deleted_by', postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column('profil_id', postgresql.UUID(as_uuid=True),
                  sa.ForeignKey('profils_locaux.id', ondelete='CASCADE'), nullable=False, index=True),
        sa.Column('groupe_id', postgresql.UUID(as_uuid=True),
                  sa.ForeignKey('groupes.id', ondelete='CASCADE'), nullable=False, index=True),
        sa.Column('perimetre',  postgresql.JSONB(), nullable=True),
        sa.Column('statut',     sa.String(20),  server_default='active', nullable=False, index=True),
        sa.Column('date_debut', sa.DateTime(timezone=True), nullable=True),
        sa.Column('date_fin',   sa.DateTime(timezone=True), nullable=True),
        sa.Column('assigne_par',postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column('meta_data',  postgresql.JSONB(), nullable=True),
    )

    # ── 12. delegations ───────────────────────────────────────────
    op.create_table('delegations',
        sa.Column('id', postgresql.UUID(as_uuid=True), server_default=sa.text('gen_random_uuid()'), primary_key=True, index=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('created_by', postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column('updated_by', postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column('is_deleted', sa.Boolean(), server_default='false', nullable=False),
        sa.Column('deleted_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('deleted_by', postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column('delegant_id',    postgresql.UUID(as_uuid=True),
                  sa.ForeignKey('profils_locaux.id', ondelete='CASCADE'), nullable=False, index=True),
        sa.Column('delegataire_id', postgresql.UUID(as_uuid=True),
                  sa.ForeignKey('profils_locaux.id', ondelete='CASCADE'), nullable=False, index=True),
        sa.Column('role_id', postgresql.UUID(as_uuid=True),
                  sa.ForeignKey('roles.id', ondelete='RESTRICT'), nullable=True),
        sa.Column('permissions_specifiques', postgresql.JSONB(), nullable=True),
        sa.Column('perimetre',        postgresql.JSONB(), nullable=True),
        sa.Column('date_debut',       sa.DateTime(timezone=True), nullable=False),
        sa.Column('date_fin',         sa.DateTime(timezone=True), nullable=False),
        sa.Column('statut',           sa.String(20), server_default='active', nullable=False, index=True),
        sa.Column('motif',            sa.Text(), nullable=True),
        sa.Column('revoque_par',      postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column('date_revocation',  sa.DateTime(timezone=True), nullable=True),
        sa.Column('raison_revocation',sa.Text(), nullable=True),
        sa.Column('meta_data',        postgresql.JSONB(), nullable=True),
    )

    # ── 13. journal_acces ─────────────────────────────────────────
    op.create_table('journal_acces',
        sa.Column('id', postgresql.UUID(as_uuid=True), server_default=sa.text('gen_random_uuid()'), primary_key=True),
        sa.Column('timestamp',          sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False, index=True),
        sa.Column('profil_id',          postgresql.UUID(as_uuid=True), nullable=True, index=True),
        sa.Column('user_id_national',   postgresql.UUID(as_uuid=True), nullable=True, index=True),
        sa.Column('nom_affiche',        sa.String(255), nullable=True),
        sa.Column('type_action',        sa.String(50),  nullable=False, index=True),
        sa.Column('module',             sa.String(100), nullable=True),
        sa.Column('ressource',          sa.String(100), nullable=True),
        sa.Column('action',             sa.String(100), nullable=True),
        sa.Column('ressource_id',       sa.String(255), nullable=True),
        sa.Column('permission_verifiee',sa.String(200), nullable=True),
        sa.Column('perimetre_verifie',  postgresql.JSONB(), nullable=True),
        sa.Column('autorise',           sa.Boolean(),   nullable=True),
        sa.Column('raison',             sa.Text(),      nullable=True),
        sa.Column('ip_address',         sa.String(45),  nullable=True),
        sa.Column('user_agent',         sa.Text(),      nullable=True),
        sa.Column('request_id',         sa.String(100), nullable=True, index=True),
        sa.Column('session_id',         sa.String(100), nullable=True),
        sa.Column('details',            postgresql.JSONB(), nullable=True),
    )

    # ── 14. endpoint_permissions ──────────────────────────────────
    op.create_table('endpoint_permissions',
        sa.Column('id', postgresql.UUID(as_uuid=True), server_default=sa.text('gen_random_uuid()'), primary_key=True, index=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('created_by', postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column('updated_by', postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column('is_deleted', sa.Boolean(), server_default='false', nullable=False),
        sa.Column('deleted_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('deleted_by', postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column('module_code',     sa.String(100), nullable=False, index=True),
        sa.Column('module_nom',      sa.String(255), nullable=True),
        sa.Column('path',            sa.String(500), nullable=False),
        sa.Column('method',          sa.String(10),  nullable=False),
        sa.Column('permission_code', sa.String(200), nullable=True),
        sa.Column('description',     sa.Text(),      nullable=True),
        sa.Column('actif',           sa.Boolean(),   server_default='true', nullable=False),
        sa.Column('meta_data',       postgresql.JSONB(), nullable=True),
    )

    # ── 15. token_settings ────────────────────────────────────────
    op.create_table('token_settings',
        sa.Column('id',                    sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column('name',                  sa.String(100), unique=True, nullable=False),
        sa.Column('access_token_lifetime', sa.Integer(), server_default='30',    nullable=False),
        sa.Column('refresh_token_lifetime',sa.Integer(), server_default='10080', nullable=False),
        sa.Column('max_sessions_per_user', sa.Integer(), server_default='5',     nullable=False),
        sa.Column('session_ttl_hours',     sa.Integer(), server_default='24',    nullable=False),
        sa.Column('rotate_refresh_tokens', sa.Boolean(), server_default='true',  nullable=False),
        sa.Column('enable_blacklist',      sa.Boolean(), server_default='true',  nullable=False),
        sa.Column('blacklist_ttl_minutes', sa.Integer(), server_default='1440',  nullable=False),
        sa.Column('require_https',         sa.Boolean(), server_default='false', nullable=False),
        sa.Column('validate_ip',           sa.Boolean(), server_default='true',  nullable=False),
        sa.Column('validate_user_agent',   sa.Boolean(), server_default='true',  nullable=False),
        sa.Column('encrypt_tokens',        sa.Boolean(), server_default='false', nullable=False),
        sa.Column('is_active',             sa.Boolean(), server_default='true',  nullable=False),
        sa.Column('created_at', sa.DateTime(), server_default=sa.text('now()'), nullable=False),
        sa.Column('updated_at', sa.DateTime(), server_default=sa.text('now()'), nullable=False),
    )

    # ── 16. token_manager ─────────────────────────────────────────
    op.create_table('token_manager',
        sa.Column('id',                 sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column('user_id',            sa.Integer(), nullable=False, index=True),
        sa.Column('username',           sa.String(255), nullable=False),
        sa.Column('access_token_hash',  sa.String(128), nullable=False, index=True),
        sa.Column('refresh_token_hash', sa.String(128), nullable=False, index=True),
        sa.Column('created_at',         sa.DateTime(), server_default=sa.text('now()'), nullable=False),
        sa.Column('expires_at',         sa.DateTime(), nullable=False, index=True),
        sa.Column('last_used',          sa.DateTime(), nullable=True),
        sa.Column('is_active',          sa.Boolean(), server_default='true',  nullable=False),
        sa.Column('is_revoked',         sa.Boolean(), server_default='false', nullable=False),
        sa.Column('revoked_at',         sa.DateTime(), nullable=True),
        sa.Column('revoked_reason',     sa.String(255), nullable=True),
        sa.Column('session_id',         sa.String(255), nullable=True),
        sa.Column('ip_address',         sa.String(45),  nullable=True),
        sa.Column('user_agent',         sa.Text(),      nullable=True),
        sa.Column('device_id',          sa.String(255), nullable=True),
        sa.Column('device_family',      sa.String(100), nullable=True),
        sa.Column('device_brand',       sa.String(100), nullable=True),
        sa.Column('device_model',       sa.String(100), nullable=True),
        sa.Column('device_type',        sa.String(50),  nullable=True),
        sa.Column('os_family',          sa.String(100), nullable=True),
        sa.Column('os_version',         sa.String(50),  nullable=True),
        sa.Column('browser_family',     sa.String(100), nullable=True),
        sa.Column('browser_version',    sa.String(50),  nullable=True),
        sa.Column('location',           sa.String(255), nullable=True),
        sa.Column('activity_count',     sa.Integer(),   server_default='0', nullable=False),
    )

    # ══════════════════════════════════════════════════════════════
    # SEEDS — Données de référence
    # ══════════════════════════════════════════════════════════════
    now = datetime.now(timezone.utc)

    # ── Source IAM Local ──────────────────────────────────────────
    source_id = str(uuid.uuid4())
    op.execute(sa.text("""
        INSERT INTO permission_sources
            (id, code, nom, description, version, url_base, actif,
             nb_permissions, created_at, updated_at)
        VALUES
            (:id, 'iam-local', 'IAM Local',
             'Module IAM Local de etablissement', '1.0.0',
             NULL, true, 0, :now, :now)
    """), {"id": source_id, "now": now})

    # ── Permissions ───────────────────────────────────────────────
    permissions_data = [
        ("iam.permission.administrer", "Administrer les permissions", "iam", "permission", "administrer"),
        ("iam.permission.consulter",   "Consulter les permissions",   "iam", "permission", "consulter"),
        ("iam.role.creer",             "Creer un role",               "iam", "role",       "creer"),
        ("iam.role.consulter",         "Consulter les roles",         "iam", "role",       "consulter"),
        ("iam.role.modifier",          "Modifier un role",            "iam", "role",       "modifier"),
        ("iam.role.supprimer",         "Supprimer un role",           "iam", "role",       "supprimer"),
        ("iam.role.assigner",          "Assigner un role",            "iam", "role",       "assigner"),
        ("iam.role.revoquer",          "Revoquer un role",            "iam", "role",       "revoquer"),
        ("iam.groupe.creer",           "Creer un groupe",             "iam", "groupe",     "creer"),
        ("iam.groupe.consulter",       "Consulter les groupes",       "iam", "groupe",     "consulter"),
        ("iam.groupe.modifier",        "Modifier un groupe",          "iam", "groupe",     "modifier"),
        ("iam.groupe.supprimer",       "Supprimer un groupe",         "iam", "groupe",     "supprimer"),
        ("iam.groupe.membre.ajouter",  "Ajouter un membre au groupe", "iam", "groupe",     "membre.ajouter"),
        ("iam.groupe.membre.retirer",  "Retirer un membre du groupe", "iam", "groupe",     "membre.retirer"),
        ("iam.profil.creer",           "Creer un profil",             "iam", "profil",     "creer"),
        ("iam.profil.consulter",       "Consulter les profils",       "iam", "profil",     "consulter"),
        ("iam.profil.modifier",        "Modifier un profil",          "iam", "profil",     "modifier"),
        ("iam.profil.suspendre",       "Suspendre un profil",         "iam", "profil",     "suspendre"),
        ("iam.profil.supprimer",       "Supprimer un profil",         "iam", "profil",     "supprimer"),
        ("iam.compte.consulter",       "Consulter les comptes",       "iam", "compte",     "consulter"),
        ("iam.compte.creer",           "Creer un compte",             "iam", "compte",     "creer"),
        ("iam.compte.modifier",        "Modifier un compte",          "iam", "compte",     "modifier"),
        ("iam.compte.suspendre",       "Suspendre un compte",         "iam", "compte",     "suspendre"),
        ("iam.compte.supprimer",       "Supprimer un compte",         "iam", "compte",     "supprimer"),
        ("iam.habilitation.consulter", "Consulter les habilitations", "iam", "habilitation","consulter"),
        ("iam.habilitation.verifier",  "Verifier une permission",     "iam", "habilitation","verifier"),
        ("iam.delegation.creer",       "Creer une delegation",        "iam", "delegation", "creer"),
        ("iam.delegation.consulter",   "Consulter les delegations",   "iam", "delegation", "consulter"),
        ("iam.delegation.revoquer",    "Revoquer une delegation",     "iam", "delegation", "revoquer"),
        ("iam.audit.consulter",        "Consulter l audit",           "iam", "audit",      "consulter"),
        ("iam.configuration.administrer","Administrer la configuration","iam","configuration","administrer"),
    ]

    perm_ids = {}
    for code, nom, domaine, ressource, action in permissions_data:
        pid = str(uuid.uuid4())
        perm_ids[code] = pid
        op.execute(sa.text("""
            INSERT INTO permissions
                (id, code, nom, domaine, ressource, action,
                 niveau_risque, actif, necessite_perimetre, deprecated,
                 source_id, created_at, updated_at)
            VALUES
                (:id, :code, :nom, :domaine, :ressource, :action,
                 'moyen', true, false, false,
                 :source_id, :now, :now)
        """), {"id": pid, "code": code, "nom": nom, "domaine": domaine,
               "ressource": ressource, "action": action,
               "source_id": source_id, "now": now})

    # Mettre à jour nb_permissions
    op.execute(sa.text(
        "UPDATE permission_sources SET nb_permissions = :n WHERE id = :id"
    ), {"n": len(perm_ids), "id": source_id})

    # ── Roles + assignation permissions ───────────────────────────
    all_perms = list(perm_ids.keys())
    roles_data = {
        "iam.admin": {
            "nom": "Administrateur IAM", "type": "systeme", "systeme": True,
            "perms": all_perms
        },
        "iam.manager": {
            "nom": "Manager IAM", "type": "fonctionnel", "systeme": False,
            "perms": [
                "iam.permission.consulter","iam.role.consulter","iam.role.assigner",
                "iam.role.revoquer","iam.groupe.consulter","iam.groupe.membre.ajouter",
                "iam.groupe.membre.retirer","iam.profil.creer","iam.profil.consulter",
                "iam.profil.modifier","iam.profil.suspendre","iam.compte.consulter",
                "iam.habilitation.consulter","iam.habilitation.verifier","iam.audit.consulter",
            ]
        },
        "iam.reader": {
            "nom": "Lecteur IAM", "type": "fonctionnel", "systeme": False,
            "perms": [
                "iam.permission.consulter","iam.role.consulter","iam.groupe.consulter",
                "iam.profil.consulter","iam.compte.consulter",
                "iam.habilitation.consulter","iam.audit.consulter",
            ]
        },
        "iam.system": {
            "nom": "Systeme IAM", "type": "systeme", "systeme": True,
            "perms": [
                "iam.habilitation.verifier","iam.profil.consulter","iam.compte.consulter",
            ]
        },
        "iam.admin_temp": {
            "nom": "Administrateur Temporaire Bootstrap",
            "type": "temporaire", "systeme": False,
            "perms": [
                "iam.profil.creer","iam.profil.consulter","iam.profil.modifier",
                "iam.compte.consulter","iam.compte.creer",
                "iam.role.consulter","iam.role.assigner",
                "iam.groupe.consulter","iam.groupe.membre.ajouter",
            ]
        },
    }

    role_ids = {}
    for code, data in roles_data.items():
        rid = str(uuid.uuid4())
        role_ids[code] = rid
        op.execute(sa.text("""
            INSERT INTO roles
                (id, code, nom, type_role, actif, systeme, created_at, updated_at)
            VALUES
                (:id, :code, :nom, :type, true, :systeme, :now, :now)
        """), {"id": rid, "code": code, "nom": data["nom"],
               "type": data["type"], "systeme": data["systeme"], "now": now})

        for pcode in data["perms"]:
            if pcode in perm_ids:
                op.execute(sa.text("""
                    INSERT INTO role_permissions (role_id, permission_id)
                    VALUES (:rid, :pid)
                """), {"rid": rid, "pid": perm_ids[pcode]})

    # ── Groupe super_admin ────────────────────────────────────────
    grp_id = str(uuid.uuid4())
    op.execute(sa.text("""
        INSERT INTO groupes
            (id, code, nom, description, type_groupe, actif, systeme, created_at, updated_at)
        VALUES
            (:id, 'super_admin', 'Super Administrateurs',
             'Groupe des super administrateurs', 'fonctionnel', true, true, :now, :now)
    """), {"id": grp_id, "now": now})

    grp_role_id = str(uuid.uuid4())
    op.execute(sa.text("""
        INSERT INTO groupe_roles (id, groupe_id, role_id, created_at, updated_at)
        VALUES (:id, :gid, :rid, :now, :now)
    """), {"id": grp_role_id, "gid": grp_id, "rid": role_ids["iam.admin"], "now": now})


def downgrade() -> None:
    op.execute(sa.text("SET session_replication_role = replica"))
    for tbl in [
        'token_manager','token_settings',
        'endpoint_permissions','journal_acces','delegations',
        'assignations_groupe','assignations_role',
        'profils_locaux','comptes_locaux',
        'groupe_roles','groupes',
        'role_permission_details','role_permissions',
        'roles','permissions','permission_sources',
    ]:
        op.execute(sa.text(f'DROP TABLE IF EXISTS "{tbl}" CASCADE'))
    op.execute(sa.text("SET session_replication_role = DEFAULT"))
