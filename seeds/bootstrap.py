"""
Bootstrap IAM Local — Orchestration idempotente.
Crée le CompteLocal + ProfilLocal bootstrap avec session Redis et token JWT.
Les permissions/rôles/groupes sont créés par la migration seed.
Peut être relancé sans risque : détecte ce qui existe déjà.
"""
import logging
from datetime import datetime, timezone, timedelta
from pathlib import Path
from typing import Optional

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, and_

from app.models.permission_source import PermissionSource
from app.models.permission import Permission
from app.models.role import Role
from app.models.groupe import Groupe
from app.models.compte_local import CompteLocal
from app.models.profil_local import ProfilLocal
from app.models.assignation_role import AssignationRole
from app.core.bootstrap_config import (
    BOOTSTRAP_IDENTIFIANT,
    BOOTSTRAP_NOM,
    BOOTSTRAP_PRENOM,
    BOOTSTRAP_EMAIL,
    BOOTSTRAP_TYPE_PROFIL,
    BOOTSTRAP_STATUT,
    ROLE_TEMP_CODE,
    IAM_SOURCE_CODE,
    BOOTSTRAP_TOKEN_EXPIRE_HOURS,
)

logger   = logging.getLogger(__name__)
DATA_DIR = Path(__file__).parent / "data"


class BootstrapService:
    """
    Orchestrateur du bootstrap IAM Local.
    Toutes les méthodes sont idempotentes.

    Responsabilités :
    - Créer le CompteLocal bootstrap (identité + credentials temporaires)
    - Créer le ProfilLocal bootstrap (rattaché au CompteLocal)
    - Assigner le rôle iam.admin_temp au ProfilLocal bootstrap
    - Créer une session Redis + générer le token JWT 48h
    - NE PAS créer permissions/rôles/groupes (fait par la migration)
    """

    def __init__(self, db: AsyncSession):
        self.db = db

    async def run(self) -> dict:
        logger.info("=" * 60)
        logger.info("BOOTSTRAP IAM LOCAL — DÉMARRAGE")
        logger.info("=" * 60)

        rapport = {
            "source"           : None,
            "permissions"      : {"crees": 0, "existantes": 0},
            "roles"            : {"crees": 0, "existants": 0},
            "groupes"          : {"crees": 0, "existants": 0},
            "profil_bootstrap" : None,
            "token"            : None,
            "deja_fait"        : False,
        }

        # ── 1. Vérifier si bootstrap déjà effectué ────────────────
        if await self._bootstrap_deja_effectue():
            logger.info("✅ Bootstrap déjà effectué — système prêt.")
            rapport["deja_fait"] = True
            profil = await self._get_profil_bootstrap()
            if profil:
                rapport["token"]            = await self._generer_token(profil)
                rapport["profil_bootstrap"] = str(profil.id)
                logger.warning(
                    "⚠️  Profil bootstrap encore actif. "
                    "Créez l'admin réel et supprimez ce profil."
                )
            return rapport

        # ── 2. Vérifier que la migration seed a été appliquée ─────
        source = await self._get_source_iam()
        if not source:
            raise Exception(
                "Source iam-local introuvable — "
                "vérifiez que la migration seed a été appliquée : "
                "alembic upgrade head"
            )
        rapport["source"] = str(source.id)

        # ── 3. Récupérer les rôles depuis la DB ───────────────────
        roles_map = await self._get_roles()
        rapport["roles"]["existants"] = len(roles_map)
        logger.info(f"   → {len(roles_map)} rôles récupérés depuis la DB")

        # ── 4. Créer le CompteLocal + ProfilLocal bootstrap ───────
        profil = await self._creer_profil_bootstrap(roles_map)
        rapport["profil_bootstrap"] = str(profil.id)

        # ── 5. Générer token + session Redis ──────────────────────
        token = await self._generer_token(profil)
        rapport["token"] = token

        await self.db.commit()

        logger.info("=" * 60)
        logger.info("✅ BOOTSTRAP TERMINÉ AVEC SUCCÈS")
        logger.info("=" * 60)
        logger.warning(
            "⚠️  TOKEN BOOTSTRAP VALIDE 48H — "
            "Créez l'admin réel puis supprimez ce profil."
        )

        return rapport

    # ── Idempotence ───────────────────────────────────────────────

    async def _bootstrap_deja_effectue(self) -> bool:
        """
        Bootstrap considéré effectué si :
        - Un admin réel (rôle iam.admin) existe, OU
        - Le CompteLocal bootstrap existe déjà
        """
        # Vérifier si un admin réel existe
        result = await self.db.execute(
            select(AssignationRole)
            .join(Role, Role.id == AssignationRole.role_id)
            .where(
                and_(
                    Role.code                  == "iam.admin",
                    AssignationRole.is_deleted == False,
                )
            )
        )
        if result.scalar_one_or_none():
            return True

        # Vérifier si le CompteLocal bootstrap existe déjà
        result = await self.db.execute(
            select(CompteLocal).where(
                and_(
                    CompteLocal.identifiant_national == BOOTSTRAP_IDENTIFIANT,
                    CompteLocal.is_deleted           == False,
                )
            )
        )
        return result.scalar_one_or_none() is not None

    async def _get_profil_bootstrap(self) -> Optional[ProfilLocal]:
        """Récupère le ProfilLocal bootstrap via son CompteLocal."""
        result = await self.db.execute(
            select(ProfilLocal)
            .join(CompteLocal, ProfilLocal.compte_id == CompteLocal.id)
            .where(
                and_(
                    CompteLocal.identifiant_national == BOOTSTRAP_IDENTIFIANT,
                    CompteLocal.statut               == BOOTSTRAP_STATUT,
                    CompteLocal.is_deleted           == False,
                    ProfilLocal.is_deleted           == False,
                )
            )
        )
        return result.scalar_one_or_none()

    # ── Récupération depuis DB ────────────────────────────────────

    async def _get_source_iam(self) -> Optional[PermissionSource]:
        result = await self.db.execute(
            select(PermissionSource).where(
                PermissionSource.code == IAM_SOURCE_CODE
            )
        )
        return result.scalar_one_or_none()

    async def _get_roles(self) -> dict:
        result = await self.db.execute(
            select(Role).where(Role.is_deleted == False)
        )
        roles = result.scalars().all()
        return {r.code: r for r in roles}

    # ── Création bootstrap ────────────────────────────────────────

    async def _creer_profil_bootstrap(self, roles_map: dict) -> ProfilLocal:
        """
        Crée le CompteLocal bootstrap + ProfilLocal bootstrap.
        Le CompteLocal porte les credentials et l'identité.
        Le ProfilLocal est l'unité centrale pour les tokens/sessions/permissions.
        """
        from app.services.profil_service import ProfilService
        from app.schemas.profil_local import ProfilLocalWithCredentialsCreateSchema

        service = ProfilService(self.db)

        bootstrap_data = ProfilLocalWithCredentialsCreateSchema(
            nom                     = BOOTSTRAP_NOM,
            prenom                  = BOOTSTRAP_PRENOM,
            email                   = BOOTSTRAP_EMAIL,
            telephone               = None,
            identifiant_national    = BOOTSTRAP_IDENTIFIANT,
            type_profil             = BOOTSTRAP_TYPE_PROFIL,
            username                = "bootstrap",
            password                = "BootstrapTemp@2024!",
            require_password_change = False,
            meta_data = {
                "bootstrap"   : True,
                "cree_le"     : datetime.now(timezone.utc).isoformat(),
                "expire_le"   : (
                    datetime.now(timezone.utc)
                    + timedelta(hours=BOOTSTRAP_TOKEN_EXPIRE_HOURS)
                ).isoformat(),
                "instructions": (
                    "1. POST /api/v1/profils/ — créer admin réel "
                    "2. POST /api/v1/profils/{id}/roles — assigner iam.admin "
                    "3. Connecter l'admin réel "
                    "4. Ce profil sera supprimé automatiquement"
                ),
                "created_by"  : "system_bootstrap",
                "role"        : ROLE_TEMP_CODE,
            },
            notes = (
                "Profil temporaire créé au bootstrap. "
                "DOIT ÊTRE SUPPRIMÉ après création de l'admin réel."
            ),
        )

        # creer_avec_credentials crée CompteLocal + ProfilLocal
        profil_response = await service.creer_avec_credentials(
            data       = bootstrap_data,
            cree_par   = None,
            request_id = "bootstrap_initialization",
        )

        # Marquer le CompteLocal comme bootstrap
        from app.repositories.compte_local import CompteLocalRepository
        compte_repo = CompteLocalRepository(self.db)
        compte = await compte_repo.get_by_id(profil_response.compte_id)
        if compte:
            await compte_repo.update(compte, {"statut": BOOTSTRAP_STATUT})

        # Récupérer le ProfilLocal ORM (pas le schema) pour la suite
        from app.repositories.profil_local import ProfilLocalRepository
        profil_repo = ProfilLocalRepository(self.db)
        profil = await profil_repo.get_by_id(profil_response.id)

        # Mettre le statut bootstrap sur le profil aussi
        await profil_repo.update(profil, {"statut": BOOTSTRAP_STATUT})

        # Assigner le rôle iam.admin_temp au ProfilLocal
        role_temp = roles_map.get(ROLE_TEMP_CODE)
        if role_temp:
            from app.schemas.assignation import AssignationRoleCreateSchema
            assignation_data = AssignationRoleCreateSchema(
                profil_id          = profil.id,
                role_id            = role_temp.id,
                raison_assignation = "Bootstrap automatique — rôle temporaire"
            )
            await service.assigner_role(
                data       = assignation_data,
                created_by = profil.id,
                request_id = "bootstrap_initialization"
            )
            logger.info(
                f"   ✅ ProfilLocal bootstrap créé — "
                f"rôle {ROLE_TEMP_CODE} assigné"
            )
        else:
            logger.error(
                f"   ❌ Rôle {ROLE_TEMP_CODE} introuvable — "
                "vérifiez la migration seed"
            )

        return profil

    # ── Token JWT + Session Redis ─────────────────────────────────

    async def _generer_token(self, profil: ProfilLocal) -> str:
        """
        Génère un token bootstrap via TokenManager.
        sub = profil.id  (unité centrale, cohérent avec tout le système)
        Durée : 48h.
        """
        from app.services.token_manager.access_token_service import AccessTokenService
        from app.services.token_manager.session_manager import SessionManager
        from app.infrastructure.cache.redis import CacheService
        from app.models.role import role_permissions_table
        from sqlalchemy import select, and_

        # ── 1. Récupérer les permissions du rôle iam.admin_temp ───────
        result = await self.db.execute(
            select(Permission)
            .join(
                role_permissions_table,
                Permission.id == role_permissions_table.c.permission_id,
            )
            .join(Role, Role.id == role_permissions_table.c.role_id)
            .where(
                and_(
                    Role.code            == ROLE_TEMP_CODE,
                    Permission.actif     == True,
                    Permission.is_deleted == False,
                )
            )
        )
        permissions      = result.scalars().all()
        permission_ids   = [str(p.id) for p in permissions]
        permission_codes = [p.code     for p in permissions]

        logger.info(
            f"   → {len(permission_ids)} permissions injectées "
            f"dans le token bootstrap : {permission_codes}"
        )

        # ── 2. Session Redis ──────────────────────────────────────────
        cache       = CacheService()
        session_mgr = SessionManager(cache)

        session_id = await session_mgr.create_session(
            user_id    = profil.id,
            user_agent = "bootstrap-system",
            ip_address = "127.0.0.1",
            metadata   = {
                "type"        : "bootstrap",
                "temporary"   : True,
                "auto_cleanup": True,
            },
        )

        # ── 3. JWT — sub = profil.id ──────────────────────────────────
        svc   = AccessTokenService()
        token = svc.create_token(
            user_id     = profil.id,
            session_id  = session_id,
            permissions = permission_ids,
            roles       = [ROLE_TEMP_CODE],
            type_profil = "systeme",
            custom_claims = {
                "user_id_national" : None,
                "statut"           : BOOTSTRAP_STATUT,
                "groupes"          : [],
                "is_bootstrap"     : True,
                "permission_codes" : permission_codes,
            },
            expires_minutes = BOOTSTRAP_TOKEN_EXPIRE_HOURS * 60,
        )

        logger.info(
            f"   ✅ Session bootstrap créée : {session_id} (TTL: 48h)"
        )
        return token
