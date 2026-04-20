"""Initial schema — CompteLocal + ProfilLocal

Revision ID: 0001_initial_schema
Revises:
Create Date: 2026-04-18

Crée uniquement les tables. Les données de référence
(permissions, rôles, groupes, source iam-local) sont
insérées par le bootstrap via seeds/scripts/run_bootstrap.py.
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = '0001_initial_schema'
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:

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
        sa.Column('code',           sa.String(100),  nullable=False, unique=True, index=True),
        sa.Column('nom',            sa.String(255),  nullable=False),
        sa.Column('description',    sa.Text(),       nullable=True),
        sa.Column('version',        sa.String(50),   nullable=True),
        sa.Column('url_base',       sa.String(500),  nullable=True),
        sa.Column('actif',          sa.Boolean(),    server_default='true', nullable=False),
        sa.Column('derniere_sync',  sa.String(50),   nullable=True),
        sa.Column('nb_permissions', sa.Integer(),    server_default='0', nullable=False),
        sa.Column('meta_data',      postgresql.JSONB(), nullable=True),
        sa.Column('notes',          sa.Text(),       nullable=True),
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
        sa.Column('code',                  sa.String(100), nullable=False, unique=True, index=True),
        sa.Column('nom',                   sa.String(255), nullable=False),
        sa.Column('description',           sa.Text(),      nullable=True),
        sa.Column('type_role',             sa.String(50),  server_default='fonctionnel', nullable=False),
        sa.Column('perimetre_obligatoire', sa.Boolean(),   server_default='false', nullable=False),
        sa.Column('perimetre_schema',      postgresql.JSONB(), nullable=True),
        sa.Column('actif',                 sa.Boolean(),   server_default='true',  nullable=False),
        sa.Column('systeme',               sa.Boolean(),   server_default='false', nullable=False),
        sa.Column('meta_data',             postgresql.JSONB(), nullable=True),
        sa.Column('notes',                 sa.Text(),      nullable=True),
    )

    # ── 4. role_permissions ───────────────────────────────────────
    op.create_table('role_permissions',
        sa.Column('role_id',       postgresql.UUID(as_uuid=True),
                  sa.ForeignKey('roles.id',       ondelete='CASCADE'), primary_key=True),
        sa.Column('permission_id', postgresql.UUID(as_uuid=True),
                  sa.ForeignKey('permissions.id', ondelete='CASCADE'), primary_key=True),
    )

    # ── 5. role_permission_details ────────────────────────────────
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
        sa.Column('role_id',   postgresql.UUID(as_uuid=True),
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
        sa.Column('user_id_national',        postgresql.UUID(as_uuid=True), nullable=True, unique=True, index=True),
        sa.Column('nom',                     sa.String(255), nullable=True),
        sa.Column('prenom',                  sa.String(255), nullable=True),
        sa.Column('email',                   sa.String(255), nullable=True, index=True),
        sa.Column('telephone',               sa.String(50),  nullable=True),
        sa.Column('identifiant_national',    sa.String(100), nullable=True, index=True),
        sa.Column('username',                sa.String(150), nullable=True, unique=True, index=True),
        sa.Column('statut',                  sa.String(20),  server_default='actif', nullable=False, index=True),
        sa.Column('raison_suspension',       sa.Text(),      nullable=True),
        sa.Column('derniere_connexion',      sa.DateTime(timezone=True), nullable=True),
        sa.Column('nb_connexions',           sa.String(20),  server_default='0', nullable=True),
        sa.Column('premiere_connexion',      sa.DateTime(timezone=True), nullable=True),
        sa.Column('password_hash',           sa.String(255), nullable=True),
        sa.Column('password_salt',           sa.String(255), nullable=True),
        sa.Column('password_algorithm',      sa.String(50),  server_default='bcrypt', nullable=True),
        sa.Column('password_changed_at',     sa.DateTime(timezone=True), nullable=True),
        sa.Column('failed_login_attempts',   sa.Integer(),   server_default='0', nullable=False),
        sa.Column('locked_until',            sa.DateTime(timezone=True), nullable=True),
        sa.Column('require_password_change', sa.Boolean(),   server_default='false', nullable=False),
        sa.Column('snapshot_iam_central',    postgresql.JSONB(), nullable=True),
        sa.Column('preferences',             postgresql.JSONB(), nullable=True),
        sa.Column('meta_data',               postgresql.JSONB(), nullable=True),
        sa.Column('notes',                   sa.Text(), nullable=True),
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
        sa.Column('username',             sa.String(150), nullable=True, unique=True, index=True),
        sa.Column('type_profil',          sa.String(50),  server_default='invite', nullable=False, index=True),
        sa.Column('statut',               sa.String(20),  server_default='actif',  nullable=False, index=True),
        sa.Column('raison_suspension',    sa.Text(),      nullable=True),
        sa.Column('derniere_connexion',   sa.DateTime(timezone=True), nullable=True),
        sa.Column('nb_connexions',        sa.String(20),  server_default='0', nullable=True),
        sa.Column('premiere_connexion',   sa.DateTime(timezone=True), nullable=True),
        sa.Column('contexte_scolaire',    postgresql.JSONB(), nullable=True),
        sa.Column('preferences',          postgresql.JSONB(), nullable=True),
        sa.Column('meta_data',            postgresql.JSONB(), nullable=True),
        sa.Column('notes',                sa.Text(), nullable=True),
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
        sa.Column('role_id',   postgresql.UUID(as_uuid=True),
                  sa.ForeignKey('roles.id', ondelete='RESTRICT'), nullable=False, index=True),
        sa.Column('perimetre',           postgresql.JSONB(), nullable=True),
        sa.Column('statut',              sa.String(20),  server_default='active', nullable=False, index=True),
        sa.Column('date_debut',          sa.DateTime(timezone=True), nullable=True),
        sa.Column('date_fin',            sa.DateTime(timezone=True), nullable=True),
        sa.Column('assigne_par',         postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column('revoque_par',         postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column('date_revocation',     sa.DateTime(timezone=True), nullable=True),
        sa.Column('raison_revocation',   sa.Text(), nullable=True),
        sa.Column('raison_assignation',  sa.Text(), nullable=True),
        sa.Column('meta_data',           postgresql.JSONB(), nullable=True),
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
        sa.Column('perimetre',   postgresql.JSONB(), nullable=True),
        sa.Column('statut',      sa.String(20),  server_default='active', nullable=False, index=True),
        sa.Column('date_debut',  sa.DateTime(timezone=True), nullable=True),
        sa.Column('date_fin',    sa.DateTime(timezone=True), nullable=True),
        sa.Column('assigne_par', postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column('meta_data',   postgresql.JSONB(), nullable=True),
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
        sa.Column('perimetre',         postgresql.JSONB(), nullable=True),
        sa.Column('date_debut',        sa.DateTime(timezone=True), nullable=False),
        sa.Column('date_fin',          sa.DateTime(timezone=True), nullable=False),
        sa.Column('statut',            sa.String(20), server_default='active', nullable=False, index=True),
        sa.Column('motif',             sa.Text(), nullable=True),
        sa.Column('revoque_par',       postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column('date_revocation',   sa.DateTime(timezone=True), nullable=True),
        sa.Column('raison_revocation', sa.Text(), nullable=True),
        sa.Column('meta_data',         postgresql.JSONB(), nullable=True),
    )

    # ── 13. journal_acces ─────────────────────────────────────────
    op.create_table('journal_acces',
        sa.Column('id', postgresql.UUID(as_uuid=True), server_default=sa.text('gen_random_uuid()'), primary_key=True),
        sa.Column('timestamp',           sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False, index=True),
        sa.Column('profil_id',           postgresql.UUID(as_uuid=True), nullable=True, index=True),
        sa.Column('user_id_national',    postgresql.UUID(as_uuid=True), nullable=True, index=True),
        sa.Column('nom_affiche',         sa.String(255), nullable=True),
        sa.Column('type_action',         sa.String(50),  nullable=False, index=True),
        sa.Column('module',              sa.String(100), nullable=True),
        sa.Column('ressource',           sa.String(100), nullable=True),
        sa.Column('action',              sa.String(100), nullable=True),
        sa.Column('ressource_id',        sa.String(255), nullable=True),
        sa.Column('permission_verifiee', sa.String(200), nullable=True),
        sa.Column('perimetre_verifie',   postgresql.JSONB(), nullable=True),
        sa.Column('autorise',            sa.Boolean(),   nullable=True),
        sa.Column('raison',              sa.Text(),      nullable=True),
        sa.Column('ip_address',          sa.String(45),  nullable=True),
        sa.Column('user_agent',          sa.Text(),      nullable=True),
        sa.Column('request_id',          sa.String(100), nullable=True, index=True),
        sa.Column('session_id',          sa.String(100), nullable=True),
        sa.Column('details',             postgresql.JSONB(), nullable=True),
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
        sa.Column('source_id', postgresql.UUID(as_uuid=True),
                  sa.ForeignKey('permission_sources.id', ondelete='CASCADE'),
                  nullable=False, index=True),
        sa.Column('path',             sa.String(500), nullable=False),
        sa.Column('method',           sa.String(10),  nullable=False),
        sa.Column('permission_uuids', postgresql.ARRAY(postgresql.UUID(as_uuid=True)),
                  nullable=False, server_default='{}'),
        sa.Column('description',      sa.Text(),      nullable=True),
        sa.Column('public',           sa.Boolean(),   server_default='false', nullable=False),
        sa.Column('actif',            sa.Boolean(),   server_default='true',  nullable=False),
        sa.Column('notes',            sa.Text(),      nullable=True),
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


def downgrade() -> None:
    op.drop_table('token_manager')
    op.drop_table('token_settings')
    op.drop_table('endpoint_permissions')
    op.drop_table('journal_acces')
    op.drop_table('delegations')
    op.drop_table('assignations_groupe')
    op.drop_table('assignations_role')
    op.drop_table('profils_locaux')
    op.drop_table('comptes_locaux')
    op.drop_table('groupe_roles')
    op.drop_table('groupes')
    op.drop_table('role_permission_details')
    op.drop_table('role_permissions')
    op.drop_table('roles')
    op.drop_table('permissions')
    op.drop_table('permission_sources')
