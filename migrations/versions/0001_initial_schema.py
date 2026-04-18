"""Initial schema complet — CompteLocal + ProfilLocal + seeds

Revision ID: 0001_initial_schema
Revises: 
Create Date: 2026-04-18

Migration unique qui repart de zéro :
  1. Supprime les tables de l'ancien schéma si elles existent
  2. Crée toutes les tables du nouveau schéma (CompteLocal + ProfilLocal séparés)
  3. Insère les données de référence (source IAM, permissions, rôles, groupes)
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql
import uuid
from datetime import datetime, timezone

# revision identifiers
revision = '0001_initial_schema'
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    # ══════════════════════════════════════════════════════════════
    # 0. NETTOYAGE — Supprimer les tables de l'ancien schéma
    #    (si la DB était déjà utilisée avec l'ancien modèle)
    # ══════════════════════════════════════════════════════════════
    conn = op.get_bind()

    # Désactiver les contraintes FK pendant le nettoyage
    conn.execute(sa.text("SET session_replication_role = replica"))

    tables_to_drop = [
        'journal_acces',
        'delegations',
        'assignations_groupe',
        'assignations_role',
        'endpoint_permissions',
        'groupe_roles',
        'groupes',
        'role_permissions',
        'roles',
        'permissions',
        'permission_sources',
        'profils_locaux',
        'comptes_locaux',
        'token_manager_records',
        'token_settings',
        'alembic_version',
    ]

    for table in tables_to_drop:
        conn.execute(sa.text(f'DROP TABLE IF EXISTS "{table}" CASCADE'))

    conn.execute(sa.text("SET session_replication_role = DEFAULT"))

    # ══════════════════════════════════════════════════════════════
    # 1. TABLE : permission_sources
    # ══════════════════════════════════════════════════════════════
    op.create_table(
        'permission_sources',
        sa.Column('id', postgresql.UUID(as_uuid=True), server_default=sa.text('gen_random_uuid()'), primary_key=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('created_by', postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column('updated_by', postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column('is_deleted', sa.Boolean(), server_default='false', nullable=False),
        sa.Column('deleted_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('deleted_by', postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column('code', sa.String(100), nullable=False, unique=True, index=True),
        sa.Column('nom', sa.String(255), nullable=False),
        sa.Column('description', sa.Text(), nullable=True),
        sa.Column('version', sa.String(50), nullable=True),
        sa.Column('url', sa.String(500), nullable=True),
        sa.Column('actif', sa.Boolean(), server_default='true', nullable=False),
        sa.Column('meta_data', postgresql.JSONB(), nullable=True),
    )

    # ══════════════════════════════════════════════════════════════
    # 2. TABLE : permissions
    # ══════════════════════════════════════════════════════════════
    op.create_table(
        'permissions',
        sa.Column('id', postgresql.UUID(as_uuid=True), server_default=sa.text('gen_random_uuid()'), primary_key=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('created_by', postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column('updated_by', postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column('is_deleted', sa.Boolean(), server_default='false', nullable=False),
        sa.Column('deleted_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('deleted_by', postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column('code', sa.String(200), nullable=False, unique=True, index=True),
        sa.Column('nom', sa.String(255), nullable=False),
        sa.Column('description', sa.Text(), nullable=True),
        sa.Column('domaine', sa.String(100), nullable=True, index=True),
        sa.Column('ressource', sa.String(100), nullable=True),
        sa.Column('action', sa.String(100), nullable=True),
        sa.Column('actif', sa.Boolean(), server_default='true', nullable=False),
        sa.Column('source_id', postgresql.UUID(as_uuid=True),
                  sa.ForeignKey('permission_sources.id', ondelete='SET NULL'), nullable=True),
        sa.Column('meta_data', postgresql.JSONB(), nullable=True),
    )

    # ══════════════════════════════════════════════════════════════
    # 3. TABLE : roles
    # ══════════════════════════════════════════════════════════════
    op.create_table(
        'roles',
        sa.Column('id', postgresql.UUID(as_uuid=True), server_default=sa.text('gen_random_uuid()'), primary_key=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('created_by', postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column('updated_by', postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column('is_deleted', sa.Boolean(), server_default='false', nullable=False),
        sa.Column('deleted_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('deleted_by', postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column('code', sa.String(100), nullable=False, unique=True, index=True),
        sa.Column('nom', sa.String(255), nullable=False),
        sa.Column('description', sa.Text(), nullable=True),
        sa.Column('type_role', sa.String(50), nullable=True, server_default='fonctionnel'),
        sa.Column('perimetre_obligatoire', sa.Boolean(), server_default='false', nullable=False),
        sa.Column('actif', sa.Boolean(), server_default='true', nullable=False),
        sa.Column('meta_data', postgresql.JSONB(), nullable=True),
    )

    # ══════════════════════════════════════════════════════════════
    # 4. TABLE : role_permissions (association)
    # ══════════════════════════════════════════════════════════════
    op.create_table(
        'role_permissions',
        sa.Column('role_id', postgresql.UUID(as_uuid=True),
                  sa.ForeignKey('roles.id', ondelete='CASCADE'), nullable=False, primary_key=True),
        sa.Column('permission_id', postgresql.UUID(as_uuid=True),
                  sa.ForeignKey('permissions.id', ondelete='CASCADE'), nullable=False, primary_key=True),
    )

    # ══════════════════════════════════════════════════════════════
    # 5. TABLE : groupes
    # ══════════════════════════════════════════════════════════════
    op.create_table(
        'groupes',
        sa.Column('id', postgresql.UUID(as_uuid=True), server_default=sa.text('gen_random_uuid()'), primary_key=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('created_by', postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column('updated_by', postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column('is_deleted', sa.Boolean(), server_default='false', nullable=False),
        sa.Column('deleted_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('deleted_by', postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column('code', sa.String(100), nullable=False, unique=True, index=True),
        sa.Column('nom', sa.String(255), nullable=False),
        sa.Column('description', sa.Text(), nullable=True),
        sa.Column('type_groupe', sa.String(50), nullable=True),
        sa.Column('perimetre', postgresql.JSONB(), nullable=True),
        sa.Column('actif', sa.Boolean(), server_default='true', nullable=False),
        sa.Column('meta_data', postgresql.JSONB(), nullable=True),
    )

    # ══════════════════════════════════════════════════════════════
    # 6. TABLE : groupe_roles (association)
    # ══════════════════════════════════════════════════════════════
    op.create_table(
        'groupe_roles',
        sa.Column('groupe_id', postgresql.UUID(as_uuid=True),
                  sa.ForeignKey('groupes.id', ondelete='CASCADE'), nullable=False, primary_key=True),
        sa.Column('role_id', postgresql.UUID(as_uuid=True),
                  sa.ForeignKey('roles.id', ondelete='CASCADE'), nullable=False, primary_key=True),
    )

    # ══════════════════════════════════════════════════════════════
    # 7. TABLE : comptes_locaux  (NOUVEAU — identité + credentials)
    # ══════════════════════════════════════════════════════════════
    op.create_table(
        'comptes_locaux',
        sa.Column('id', postgresql.UUID(as_uuid=True), server_default=sa.text('gen_random_uuid()'), primary_key=True, index=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('created_by', postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column('updated_by', postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column('is_deleted', sa.Boolean(), server_default='false', nullable=False),
        sa.Column('deleted_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('deleted_by', postgresql.UUID(as_uuid=True), nullable=True),
        # Lien IAM Central
        sa.Column('user_id_national', postgresql.UUID(as_uuid=True), nullable=True, unique=True, index=True),
        # Identité (synchronisée depuis IAM Central)
        sa.Column('nom', sa.String(255), nullable=True),
        sa.Column('prenom', sa.String(255), nullable=True),
        sa.Column('email', sa.String(255), nullable=True, index=True),
        sa.Column('telephone', sa.String(50), nullable=True),
        sa.Column('identifiant_national', sa.String(100), nullable=True, index=True),
        sa.Column('username', sa.String(150), nullable=True, unique=True, index=True),
        # Statut
        sa.Column('statut', sa.String(20), server_default='actif', nullable=False, index=True),
        sa.Column('raison_suspension', sa.Text(), nullable=True),
        # Métadonnées de connexion
        sa.Column('derniere_connexion', sa.DateTime(timezone=True), nullable=True),
        sa.Column('nb_connexions', sa.String(20), nullable=True, server_default='0'),
        sa.Column('premiere_connexion', sa.DateTime(timezone=True), nullable=True),
        # Credentials locaux
        sa.Column('password_hash', sa.String(255), nullable=True),
        sa.Column('password_salt', sa.String(255), nullable=True),
        sa.Column('password_algorithm', sa.String(50), nullable=True, server_default='bcrypt'),
        sa.Column('password_changed_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('failed_login_attempts', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('locked_until', sa.DateTime(timezone=True), nullable=True),
        sa.Column('require_password_change', sa.Boolean(), nullable=False, server_default='false'),
        # Snapshot IAM Central
        sa.Column('snapshot_iam_central', postgresql.JSONB(), nullable=True),
        # Divers
        sa.Column('preferences', postgresql.JSONB(), nullable=True),
        sa.Column('meta_data', postgresql.JSONB(), nullable=True),
        sa.Column('notes', sa.Text(), nullable=True),
    )

    # ══════════════════════════════════════════════════════════════
    # 8. TABLE : profils_locaux  (REFACTORISÉ — inscription + droits)
    # ══════════════════════════════════════════════════════════════
    op.create_table(
        'profils_locaux',
        sa.Column('id', postgresql.UUID(as_uuid=True), server_default=sa.text('gen_random_uuid()'), primary_key=True, index=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('created_by', postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column('updated_by', postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column('is_deleted', sa.Boolean(), server_default='false', nullable=False),
        sa.Column('deleted_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('deleted_by', postgresql.UUID(as_uuid=True), nullable=True),
        # FK vers CompteLocal
        sa.Column('compte_id', postgresql.UUID(as_uuid=True),
                  sa.ForeignKey('comptes_locaux.id', ondelete='CASCADE'), nullable=False, index=True),
        # Identifiant de connexion dénormalisé
        sa.Column('username', sa.String(150), nullable=True, unique=True, index=True),
        # Type et statut
        sa.Column('type_profil', sa.String(50), nullable=False, server_default='invite', index=True),
        sa.Column('statut', sa.String(20), nullable=False, server_default='actif', index=True),
        sa.Column('raison_suspension', sa.Text(), nullable=True),
        # Métadonnées de session (par profil)
        sa.Column('derniere_connexion', sa.DateTime(timezone=True), nullable=True),
        sa.Column('nb_connexions', sa.String(20), nullable=True, server_default='0'),
        sa.Column('premiere_connexion', sa.DateTime(timezone=True), nullable=True),
        # Contexte scolaire spécifique à ce profil
        sa.Column('contexte_scolaire', postgresql.JSONB(), nullable=True),
        # Divers
        sa.Column('preferences', postgresql.JSONB(), nullable=True),
        sa.Column('meta_data', postgresql.JSONB(), nullable=True),
        sa.Column('notes', sa.Text(), nullable=True),
    )

    # ══════════════════════════════════════════════════════════════
    # 9. TABLE : assignations_role
    # ══════════════════════════════════════════════════════════════
    op.create_table(
        'assignations_role',
        sa.Column('id', postgresql.UUID(as_uuid=True), server_default=sa.text('gen_random_uuid()'), primary_key=True),
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
        sa.Column('perimetre', postgresql.JSONB(), nullable=True),
        sa.Column('statut', sa.String(20), nullable=False, server_default='active', index=True),
        sa.Column('date_debut', sa.DateTime(timezone=True), nullable=True),
        sa.Column('date_fin', sa.DateTime(timezone=True), nullable=True),
        sa.Column('assigne_par', postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column('revoque_par', postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column('date_revocation', sa.DateTime(timezone=True), nullable=True),
        sa.Column('raison_revocation', sa.Text(), nullable=True),
        sa.Column('raison_assignation', sa.Text(), nullable=True),
        sa.Column('meta_data', postgresql.JSONB(), nullable=True),
    )

    # ══════════════════════════════════════════════════════════════
    # 10. TABLE : assignations_groupe
    # ══════════════════════════════════════════════════════════════
    op.create_table(
        'assignations_groupe',
        sa.Column('id', postgresql.UUID(as_uuid=True), server_default=sa.text('gen_random_uuid()'), primary_key=True),
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
        sa.Column('perimetre', postgresql.JSONB(), nullable=True),
        sa.Column('statut', sa.String(20), nullable=False, server_default='active', index=True),
        sa.Column('date_debut', sa.DateTime(timezone=True), nullable=True),
        sa.Column('date_fin', sa.DateTime(timezone=True), nullable=True),
        sa.Column('assigne_par', postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column('meta_data', postgresql.JSONB(), nullable=True),
    )

    # ══════════════════════════════════════════════════════════════
    # 11. TABLE : delegations
    # ══════════════════════════════════════════════════════════════
    op.create_table(
        'delegations',
        sa.Column('id', postgresql.UUID(as_uuid=True), server_default=sa.text('gen_random_uuid()'), primary_key=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('created_by', postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column('updated_by', postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column('is_deleted', sa.Boolean(), server_default='false', nullable=False),
        sa.Column('deleted_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('deleted_by', postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column('delegant_id', postgresql.UUID(as_uuid=True),
                  sa.ForeignKey('profils_locaux.id', ondelete='CASCADE'), nullable=False, index=True),
        sa.Column('delegataire_id', postgresql.UUID(as_uuid=True),
                  sa.ForeignKey('profils_locaux.id', ondelete='CASCADE'), nullable=False, index=True),
        sa.Column('role_id', postgresql.UUID(as_uuid=True),
                  sa.ForeignKey('roles.id', ondelete='RESTRICT'), nullable=True),
        sa.Column('permissions_specifiques', postgresql.JSONB(), nullable=True),
        sa.Column('perimetre', postgresql.JSONB(), nullable=True),
        sa.Column('date_debut', sa.DateTime(timezone=True), nullable=False),
        sa.Column('date_fin', sa.DateTime(timezone=True), nullable=False),
        sa.Column('statut', sa.String(20), nullable=False, server_default='active', index=True),
        sa.Column('motif', sa.Text(), nullable=True),
        sa.Column('revoque_par', postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column('date_revocation', sa.DateTime(timezone=True), nullable=True),
        sa.Column('raison_revocation', sa.Text(), nullable=True),
        sa.Column('meta_data', postgresql.JSONB(), nullable=True),
    )

    # ══════════════════════════════════════════════════════════════
    # 12. TABLE : journal_acces  (audit immuable)
    # ══════════════════════════════════════════════════════════════
    op.create_table(
        'journal_acces',
        sa.Column('id', postgresql.UUID(as_uuid=True), server_default=sa.text('gen_random_uuid()'), primary_key=True),
        sa.Column('timestamp', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False, index=True),
        sa.Column('profil_id', postgresql.UUID(as_uuid=True), nullable=True, index=True),
        sa.Column('user_id_national', postgresql.UUID(as_uuid=True), nullable=True, index=True),
        sa.Column('nom_affiche', sa.String(255), nullable=True),
        sa.Column('type_action', sa.String(50), nullable=False, index=True),
        sa.Column('module', sa.String(100), nullable=True),
        sa.Column('ressource', sa.String(100), nullable=True),
        sa.Column('action', sa.String(100), nullable=True),
        sa.Column('ressource_id', sa.String(255), nullable=True),
        sa.Column('permission_verifiee', sa.String(200), nullable=True),
        sa.Column('perimetre_verifie', postgresql.JSONB(), nullable=True),
        sa.Column('autorise', sa.Boolean(), nullable=True),
        sa.Column('raison', sa.Text(), nullable=True),
        sa.Column('ip_address', sa.String(45), nullable=True),
        sa.Column('user_agent', sa.Text(), nullable=True),
        sa.Column('request_id', sa.String(100), nullable=True, index=True),
        sa.Column('session_id', sa.String(100), nullable=True),
        sa.Column('details', postgresql.JSONB(), nullable=True),
    )

    # ══════════════════════════════════════════════════════════════
    # 13. TABLE : endpoint_permissions
    # ══════════════════════════════════════════════════════════════
    op.create_table(
        'endpoint_permissions',
        sa.Column('id', postgresql.UUID(as_uuid=True), server_default=sa.text('gen_random_uuid()'), primary_key=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('created_by', postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column('updated_by', postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column('is_deleted', sa.Boolean(), server_default='false', nullable=False),
        sa.Column('deleted_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('deleted_by', postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column('module_code', sa.String(100), nullable=False, index=True),
        sa.Column('module_nom', sa.String(255), nullable=True),
        sa.Column('path', sa.String(500), nullable=False),
        sa.Column('method', sa.String(10), nullable=False),
        sa.Column('permission_code', sa.String(200), nullable=True),
        sa.Column('description', sa.Text(), nullable=True),
        sa.Column('actif', sa.Boolean(), server_default='true', nullable=False),
        sa.Column('meta_data', postgresql.JSONB(), nullable=True),
    )

    # ══════════════════════════════════════════════════════════════
    # 14. TABLE : token_settings
    # ══════════════════════════════════════════════════════════════
    op.create_table(
        'token_settings',
        sa.Column('id', postgresql.UUID(as_uuid=True), server_default=sa.text('gen_random_uuid()'), primary_key=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('name', sa.String(255), nullable=False),
        sa.Column('access_token_lifetime', sa.Integer(), nullable=False, server_default='30'),
        sa.Column('refresh_token_lifetime', sa.Integer(), nullable=False, server_default='43200'),
        sa.Column('max_sessions_per_user', sa.Integer(), nullable=False, server_default='5'),
        sa.Column('session_ttl_hours', sa.Integer(), nullable=False, server_default='24'),
        sa.Column('rotate_refresh_tokens', sa.Boolean(), server_default='true', nullable=False),
        sa.Column('enable_blacklist', sa.Boolean(), server_default='true', nullable=False),
        sa.Column('blacklist_ttl_minutes', sa.Integer(), nullable=False, server_default='1440'),
        sa.Column('require_https', sa.Boolean(), server_default='false', nullable=False),
        sa.Column('validate_ip', sa.Boolean(), server_default='false', nullable=False),
        sa.Column('validate_user_agent', sa.Boolean(), server_default='false', nullable=False),
        sa.Column('encrypt_tokens', sa.Boolean(), server_default='false', nullable=False),
        sa.Column('is_active', sa.Boolean(), server_default='false', nullable=False),
    )

    # ══════════════════════════════════════════════════════════════
    # 15. TABLE : token_manager_records
    # ══════════════════════════════════════════════════════════════
    op.create_table(
        'token_manager_records',
        sa.Column('id', postgresql.UUID(as_uuid=True), server_default=sa.text('gen_random_uuid()'), primary_key=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('settings_id', postgresql.UUID(as_uuid=True),
                  sa.ForeignKey('token_settings.id', ondelete='SET NULL'), nullable=True),
        sa.Column('action', sa.String(100), nullable=False),
        sa.Column('details', postgresql.JSONB(), nullable=True),
        sa.Column('performed_by', postgresql.UUID(as_uuid=True), nullable=True),
    )

    # ══════════════════════════════════════════════════════════════
    # SEEDS — Données de référence
    # ══════════════════════════════════════════════════════════════

    conn = op.get_bind()
    now = datetime.now(timezone.utc)

    # ── Source IAM Local ──────────────────────────────────────────
    source_id = str(uuid.uuid4())
    conn.execute(sa.text("""
        INSERT INTO permission_sources (id, code, nom, description, version, actif, created_at, updated_at)
        VALUES (:id, :code, :nom, :desc, :version, true, :now, :now)
    """), {"id": source_id, "code": "iam-local",
           "nom": "IAM Local", "desc": "Module IAM Local de l'établissement",
           "version": "1.0.0", "now": now})

    # ── Permissions ───────────────────────────────────────────────
    permissions_data = [
        ("iam.permission.administrer", "Administrer les permissions", "iam", "permission", "administrer"),
        ("iam.permission.consulter",   "Consulter les permissions",   "iam", "permission", "consulter"),
        ("iam.role.creer",             "Créer un rôle",               "iam", "role",       "creer"),
        ("iam.role.consulter",         "Consulter les rôles",         "iam", "role",       "consulter"),
        ("iam.role.modifier",          "Modifier un rôle",            "iam", "role",       "modifier"),
        ("iam.role.supprimer",         "Supprimer un rôle",           "iam", "role",       "supprimer"),
        ("iam.role.assigner",          "Assigner un rôle",            "iam", "role",       "assigner"),
        ("iam.role.revoquer",          "Révoquer un rôle",            "iam", "role",       "revoquer"),
        ("iam.groupe.creer",           "Créer un groupe",             "iam", "groupe",     "creer"),
        ("iam.groupe.consulter",       "Consulter les groupes",       "iam", "groupe",     "consulter"),
        ("iam.groupe.modifier",        "Modifier un groupe",          "iam", "groupe",     "modifier"),
        ("iam.groupe.supprimer",       "Supprimer un groupe",         "iam", "groupe",     "supprimer"),
        ("iam.groupe.membre.ajouter",  "Ajouter un membre au groupe", "iam", "groupe",     "membre.ajouter"),
        ("iam.groupe.membre.retirer",  "Retirer un membre du groupe", "iam", "groupe",     "membre.retirer"),
        ("iam.profil.creer",           "Créer un profil",             "iam", "profil",     "creer"),
        ("iam.profil.consulter",       "Consulter les profils",       "iam", "profil",     "consulter"),
        ("iam.profil.modifier",        "Modifier un profil",          "iam", "profil",     "modifier"),
        ("iam.profil.suspendre",       "Suspendre un profil",         "iam", "profil",     "suspendre"),
        ("iam.profil.supprimer",       "Supprimer un profil",         "iam", "profil",     "supprimer"),
        ("iam.compte.consulter",       "Consulter les comptes",       "iam", "compte",     "consulter"),
        ("iam.compte.creer",           "Créer un compte",             "iam", "compte",     "creer"),
        ("iam.compte.modifier",        "Modifier un compte",          "iam", "compte",     "modifier"),
        ("iam.compte.suspendre",       "Suspendre un compte",         "iam", "compte",     "suspendre"),
        ("iam.compte.supprimer",       "Supprimer un compte",         "iam", "compte",     "supprimer"),
        ("iam.habilitation.consulter", "Consulter les habilitations", "iam", "habilitation","consulter"),
        ("iam.habilitation.verifier",  "Vérifier une permission",     "iam", "habilitation","verifier"),
        ("iam.delegation.creer",       "Créer une délégation",        "iam", "delegation", "creer"),
        ("iam.delegation.consulter",   "Consulter les délégations",   "iam", "delegation", "consulter"),
        ("iam.delegation.revoquer",    "Révoquer une délégation",     "iam", "delegation", "revoquer"),
        ("iam.audit.consulter",        "Consulter l'audit",          "iam", "audit",      "consulter"),
        ("iam.configuration.administrer","Administrer la configuration","iam","configuration","administrer"),
    ]

    perm_ids = {}
    for code, nom, domaine, ressource, action in permissions_data:
        pid = str(uuid.uuid4())
        perm_ids[code] = pid
        conn.execute(sa.text("""
            INSERT INTO permissions (id, code, nom, domaine, ressource, action, actif, source_id, created_at, updated_at)
            VALUES (:id, :code, :nom, :domaine, :ressource, :action, true, :source_id, :now, :now)
        """), {"id": pid, "code": code, "nom": nom, "domaine": domaine,
               "ressource": ressource, "action": action, "source_id": source_id, "now": now})

    # ── Rôles ─────────────────────────────────────────────────────
    roles_data = {
        "iam.admin": {
            "nom": "Administrateur IAM",
            "desc": "Accès complet à toutes les fonctions IAM",
            "type": "systeme",
            "perms": list(perm_ids.keys())  # toutes les permissions
        },
        "iam.manager": {
            "nom": "Manager IAM",
            "desc": "Gestion des profils, rôles et groupes",
            "type": "fonctionnel",
            "perms": ["iam.permission.consulter","iam.role.consulter","iam.role.assigner",
                      "iam.role.revoquer","iam.groupe.consulter","iam.groupe.membre.ajouter",
                      "iam.groupe.membre.retirer","iam.profil.creer","iam.profil.consulter",
                      "iam.profil.modifier","iam.profil.suspendre","iam.compte.consulter",
                      "iam.habilitation.consulter","iam.habilitation.verifier","iam.audit.consulter"]
        },
        "iam.reader": {
            "nom": "Lecteur IAM",
            "desc": "Consultation uniquement",
            "type": "fonctionnel",
            "perms": ["iam.permission.consulter","iam.role.consulter","iam.groupe.consulter",
                      "iam.profil.consulter","iam.compte.consulter","iam.habilitation.consulter",
                      "iam.audit.consulter"]
        },
        "iam.system": {
            "nom": "Système IAM",
            "desc": "Compte système pour intégrations",
            "type": "systeme",
            "perms": ["iam.habilitation.verifier","iam.profil.consulter","iam.compte.consulter"]
        },
        "iam.admin_temp": {
            "nom": "Administrateur Temporaire Bootstrap",
            "desc": "Rôle temporaire bootstrap — à supprimer après installation",
            "type": "temporaire",
            "perms": ["iam.profil.creer","iam.profil.consulter","iam.profil.modifier",
                      "iam.compte.consulter","iam.compte.creer",
                      "iam.role.consulter","iam.role.assigner",
                      "iam.groupe.consulter","iam.groupe.membre.ajouter"]
        },
    }

    role_ids = {}
    for code, data in roles_data.items():
        rid = str(uuid.uuid4())
        role_ids[code] = rid
        conn.execute(sa.text("""
            INSERT INTO roles (id, code, nom, description, type_role, actif, created_at, updated_at)
            VALUES (:id, :code, :nom, :desc, :type, true, :now, :now)
        """), {"id": rid, "code": code, "nom": data["nom"],
               "desc": data["desc"], "type": data["type"], "now": now})
        # Assigner les permissions au rôle
        for pcode in data["perms"]:
            if pcode in perm_ids:
                conn.execute(sa.text("""
                    INSERT INTO role_permissions (role_id, permission_id)
                    VALUES (:role_id, :perm_id)
                """), {"role_id": rid, "perm_id": perm_ids[pcode]})

    # ── Groupes ───────────────────────────────────────────────────
    super_admin_id = str(uuid.uuid4())
    conn.execute(sa.text("""
        INSERT INTO groupes (id, code, nom, description, type_groupe, actif, created_at, updated_at)
        VALUES (:id, :code, :nom, :desc, :type, true, :now, :now)
    """), {"id": super_admin_id, "code": "super_admin",
           "nom": "Super Administrateurs",
           "desc": "Groupe des super administrateurs de l'établissement",
           "type": "fonctionnel", "now": now})

    conn.execute(sa.text("""
        INSERT INTO groupe_roles (groupe_id, role_id) VALUES (:gid, :rid)
    """), {"gid": super_admin_id, "rid": role_ids["iam.admin"]})


def downgrade() -> None:
    tables = [
        'token_manager_records', 'token_settings',
        'endpoint_permissions', 'journal_acces', 'delegations',
        'assignations_groupe', 'assignations_role',
        'profils_locaux', 'comptes_locaux',
        'groupe_roles', 'groupes',
        'role_permissions', 'roles',
        'permissions', 'permission_sources',
    ]
    for table in tables:
        op.drop_table(table, if_exists=True)
