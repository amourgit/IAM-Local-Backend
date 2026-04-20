"""
Bootstrap IAM Local — Orchestration idempotente.
Crée les seeds (source, permissions, rôles, groupes)
puis le CompteLocal + ProfilLocal bootstrap avec session Redis et token JWT.
Peut être relancé sans risque : détecte ce qui existe déjà.
"""
import logging
import uuid
from datetime import datetime, timezone, timedelta
from pathlib import Path
from typing import Optional

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, and_, text

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
    Orchestrateur du bootstrap IAM Local. Toutes les méthodes sont idempotentes.

    Responsabilités :
    1. Créer la source IAM + permissions + rôles + groupes (seeds)
    2. Créer le CompteLocal + ProfilLocal bootstrap
    3. Assigner le rôle iam.admin_temp au profil bootstrap
    4. Créer une session Redis + générer le token JWT 48h
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
            "endpoints"        : {"crees": 0, "existants": 0},
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

        # ── 2. Charger les seeds depuis iam_seed.json ─────────────
        from seeds.seed_loader import SeedLoader
        seed_loader = SeedLoader(self.db)
        seeds_rapport = await seed_loader.run()
        await self.db.commit()

        rapport["source"]      = seeds_rapport["source"]
        rapport["permissions"] = seeds_rapport["permissions"]
        rapport["roles"]       = seeds_rapport["roles"]
        rapport["groupes"]     = seeds_rapport["groupes"]
        rapport["endpoints"]   = seeds_rapport["endpoints"]

        logger.info(
            f"   → Seeds: {seeds_rapport['permissions']['crees']} permissions, "
            f"{seeds_rapport['roles']['crees']} rôles, "
            f"{seeds_rapport['groupes']['crees']} groupes, "
            f"{seeds_rapport['endpoints']['crees']} endpoints"
        )

        # ── 3. Récupérer les rôles pour le profil bootstrap ───────
        from app.models.role import Role
        from sqlalchemy import select
        result = await self.db.execute(
            select(Role).where(Role.is_deleted == False)
        )
        roles_map = {r.code: r for r in result.scalars().all()}

        # ── 4. Créer le CompteLocal + ProfilLocal bootstrap ────────
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
        # Vérifier si un admin réel (rôle iam.admin) existe
        try:
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
        except Exception:
            pass

        # Vérifier si le CompteLocal bootstrap existe déjà
        try:
            result = await self.db.execute(
                select(CompteLocal).where(
                    and_(
                        CompteLocal.identifiant_national == BOOTSTRAP_IDENTIFIANT,
                        CompteLocal.is_deleted           == False,
                    )
                )
            )
            return result.scalar_one_or_none() is not None
        except Exception:
            return False

    async def _get_profil_bootstrap(self) -> Optional[ProfilLocal]:
        try:
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
        except Exception:
            return None

    # ── Seeds ─────────────────────────────────────────────────────

    async def _get_ou_creer_source_iam(self) -> PermissionSource:
        result = await self.db.execute(
            select(PermissionSource).where(PermissionSource.code == IAM_SOURCE_CODE)
        )
        source = result.scalar_one_or_none()
        if source:
            return source

        source = PermissionSource(
            code          = IAM_SOURCE_CODE,
            nom           = "IAM Local",
            description   = "Module IAM Local de l'établissement",
            version       = "1.0.0",
            actif         = True,
            nb_permissions= 0,
        )
        self.db.add(source)
        await self.db.flush()
        return source

    async def _get_ou_creer_permissions(self, source: PermissionSource) -> dict:
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
            ("iam.configuration.administrer","Administrer la config",     "iam", "configuration","administrer"),
        ]

        perm_map = {}
        for code, nom, domaine, ressource, action in permissions_data:
            result = await self.db.execute(
                select(Permission).where(Permission.code == code)
            )
            p = result.scalar_one_or_none()
            if not p:
                p = Permission(
                    source_id  = source.id,
                    code       = code,
                    nom        = nom,
                    domaine    = domaine,
                    ressource  = ressource,
                    action     = action,
                    actif      = True,
                )
                self.db.add(p)
                await self.db.flush()
            perm_map[code] = p

        source.nb_permissions = len(perm_map)
        self.db.add(source)
        return perm_map

    async def _get_ou_creer_roles(self, perms_map: dict) -> dict:
        all_perms = list(perms_map.keys())
        roles_data = {
            "iam.admin": {
                "nom": "Administrateur IAM", "type": "systeme", "systeme": True,
                "perms": all_perms,
            },
            "iam.manager": {
                "nom": "Manager IAM", "type": "fonctionnel", "systeme": False,
                "perms": [
                    "iam.permission.consulter","iam.role.consulter","iam.role.assigner",
                    "iam.role.revoquer","iam.groupe.consulter","iam.groupe.membre.ajouter",
                    "iam.groupe.membre.retirer","iam.profil.creer","iam.profil.consulter",
                    "iam.profil.modifier","iam.profil.suspendre","iam.compte.consulter",
                    "iam.habilitation.consulter","iam.habilitation.verifier","iam.audit.consulter",
                ],
            },
            "iam.reader": {
                "nom": "Lecteur IAM", "type": "fonctionnel", "systeme": False,
                "perms": [
                    "iam.permission.consulter","iam.role.consulter","iam.groupe.consulter",
                    "iam.profil.consulter","iam.compte.consulter",
                    "iam.habilitation.consulter","iam.audit.consulter",
                ],
            },
            "iam.system": {
                "nom": "Systeme IAM", "type": "systeme", "systeme": True,
                "perms": [
                    "iam.habilitation.verifier","iam.profil.consulter","iam.compte.consulter",
                ],
            },
            "iam.admin_temp": {
                "nom": "Administrateur Temporaire Bootstrap",
                "type": "temporaire", "systeme": False,
                "perms": [
                    "iam.profil.creer","iam.profil.consulter","iam.profil.modifier",
                    "iam.compte.consulter","iam.compte.creer",
                    "iam.role.consulter","iam.role.assigner",
                    "iam.groupe.consulter","iam.groupe.membre.ajouter",
                ],
            },
        }

        from app.models.role import role_permissions_table
        from sqlalchemy import insert

        roles_map = {}
        for code, data in roles_data.items():
            result = await self.db.execute(
                select(Role).where(Role.code == code)
            )
            role = result.scalar_one_or_none()
            if not role:
                role = Role(
                    code     = code,
                    nom      = data["nom"],
                    type_role= data["type"],
                    actif    = True,
                    systeme  = data["systeme"],
                )
                self.db.add(role)
                await self.db.flush()

                # Assigner les permissions via la table d'association
                for pcode in data["perms"]:
                    if pcode in perms_map:
                        await self.db.execute(
                            insert(role_permissions_table).values(
                                role_id       = role.id,
                                permission_id = perms_map[pcode].id,
                            )
                        )

            roles_map[code] = role

        return roles_map

    async def _get_ou_creer_groupes(self, roles_map: dict) -> None:
        from app.models.groupe import GroupeRole

        result = await self.db.execute(
            select(Groupe).where(Groupe.code == "super_admin")
        )
        groupe = result.scalar_one_or_none()
        if not groupe:
            groupe = Groupe(
                code        = "super_admin",
                nom         = "Super Administrateurs",
                description = "Groupe des super administrateurs",
                type_groupe = "fonctionnel",
                actif       = True,
                systeme     = True,
            )
            self.db.add(groupe)
            await self.db.flush()

            if "iam.admin" in roles_map:
                grp_role = GroupeRole(
                    groupe_id = groupe.id,
                    role_id   = roles_map["iam.admin"].id,
                )
                self.db.add(grp_role)

    # ── Profil bootstrap ──────────────────────────────────────────

    async def _creer_profil_bootstrap(self, roles_map: dict) -> ProfilLocal:
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
                "created_by"  : "system_bootstrap",
                "role"        : ROLE_TEMP_CODE,
            },
            notes = (
                "Profil temporaire créé au bootstrap. "
                "DOIT ÊTRE SUPPRIMÉ après création de l'admin réel."
            ),
        )

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

        # Récupérer le ProfilLocal ORM
        from app.repositories.profil_local import ProfilLocalRepository
        profil_repo = ProfilLocalRepository(self.db)
        profil = await profil_repo.get_by_id(profil_response.id)
        await profil_repo.update(profil, {"statut": BOOTSTRAP_STATUT})

        # Assigner le rôle iam.admin_temp au ProfilLocal
        role_temp = roles_map.get(ROLE_TEMP_CODE)
        if role_temp:
            from app.schemas.assignation import AssignationRoleCreateSchema
            assignation_data = AssignationRoleCreateSchema(
                profil_id          = profil.id,
                role_id            = role_temp.id,
                raison_assignation = "Bootstrap automatique — rôle temporaire",
            )
            await service.assigner_role(
                data       = assignation_data,
                created_by = profil.id,
                request_id = "bootstrap_initialization",
            )
            logger.info(f"   ✅ ProfilLocal bootstrap créé — rôle {ROLE_TEMP_CODE} assigné")
        else:
            logger.error(f"   ❌ Rôle {ROLE_TEMP_CODE} introuvable")

        return profil

    # ── Token JWT + Session Redis ─────────────────────────────────

    async def _generer_token(self, profil: ProfilLocal) -> str:
        from app.services.token_manager.access_token_service import AccessTokenService
        from app.services.token_manager.session_manager import SessionManager
        from app.infrastructure.cache.redis import CacheService
        from app.models.role import role_permissions_table

        result = await self.db.execute(
            select(Permission)
            .join(role_permissions_table,
                  Permission.id == role_permissions_table.c.permission_id)
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
        permission_codes = [p.code    for p in permissions]

        logger.info(
            f"   → {len(permission_ids)} permissions dans le token bootstrap"
        )

        cache       = CacheService()
        session_mgr = SessionManager(cache)
        session_id  = await session_mgr.create_session(
            user_id    = profil.id,
            user_agent = "bootstrap-system",
            ip_address = "127.0.0.1",
            metadata   = {"type": "bootstrap", "temporary": True},
        )

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

        logger.info(f"   ✅ Session bootstrap créée : {session_id} (TTL: 48h)")
        return token
