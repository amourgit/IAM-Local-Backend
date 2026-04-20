"""
SeedLoader — Charge et persiste les données de référence depuis seeds/data/iam_seed.json.

Principe :
- Lecture du fichier JSON unique (source of truth)
- Idempotence totale : vérification d'existence avant toute insertion
- Ordre de chargement : source → permissions → roles → groupes → endpoints
- Les permissions des rôles sont résolues par code → UUID
- $ALL = toutes les permissions de la source
- Les endpoints référencent les permissions par code → UUID[]

Utilisé par le bootstrap et potentiellement par un endpoint admin
pour re-synchroniser les données natives.
"""
import json
import logging
import uuid
from pathlib import Path
from typing import Dict, Any, List, Optional
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, insert

from app.models.permission_source import PermissionSource
from app.models.permission import Permission
from app.models.role import Role, role_permissions_table
from app.models.groupe import Groupe, GroupeRole
from app.models.endpoint_permission import EndpointPermission

logger   = logging.getLogger(__name__)
SEED_FILE = Path(__file__).parent / "data" / "iam_seed.json"


class SeedLoader:
    """
    Charge les données de référence natives depuis iam_seed.json.
    Toutes les opérations sont idempotentes (upsert par code).
    """

    def __init__(self, db: AsyncSession):
        self.db   = db
        self.data = json.loads(SEED_FILE.read_text(encoding="utf-8"))

        # Maps code → ORM object, construits au fur et à mesure
        self._perms_map  : Dict[str, Permission] = {}
        self._roles_map  : Dict[str, Role]       = {}
        self._groupes_map: Dict[str, Groupe]     = {}

    async def run(self) -> Dict[str, Any]:
        """Point d'entrée principal. Retourne un rapport d'exécution."""
        rapport = {
            "source"     : None,
            "permissions": {"crees": 0, "existantes": 0},
            "roles"      : {"crees": 0, "existants": 0},
            "groupes"    : {"crees": 0, "existants": 0},
            "endpoints"  : {"crees": 0, "existants": 0},
        }

        # 1. Source
        source = await self._load_source()
        rapport["source"] = source.code

        # 2. Permissions
        p_crees, p_exist = await self._load_permissions(source)
        rapport["permissions"] = {"crees": p_crees, "existantes": p_exist}

        # 3. Rôles
        r_crees, r_exist = await self._load_roles()
        rapport["roles"] = {"crees": r_crees, "existants": r_exist}

        # 4. Groupes
        g_crees, g_exist = await self._load_groupes()
        rapport["groupes"] = {"crees": g_crees, "existants": g_exist}

        # 5. Endpoints
        e_crees, e_exist = await self._load_endpoints(source)
        rapport["endpoints"] = {"crees": e_crees, "existants": e_exist}

        # Mettre à jour le compteur nb_permissions de la source
        source.nb_permissions = len(self._perms_map)
        self.db.add(source)
        await self.db.flush()

        logger.info(
            f"SeedLoader: {p_crees}+{p_exist} perms | "
            f"{r_crees}+{r_exist} roles | "
            f"{g_crees}+{g_exist} groupes | "
            f"{e_crees}+{e_exist} endpoints"
        )
        return rapport

    # ── Source ────────────────────────────────────────────────────

    async def _load_source(self) -> PermissionSource:
        src_data = self.data["source"]
        result   = await self.db.execute(
            select(PermissionSource).where(PermissionSource.code == src_data["code"])
        )
        source = result.scalar_one_or_none()
        if not source:
            source = PermissionSource(
                code         = src_data["code"],
                nom          = src_data["nom"],
                description  = src_data.get("description", ""),
                version      = src_data.get("version", "1.0.0"),
                actif        = True,
                nb_permissions= 0,
            )
            self.db.add(source)
            await self.db.flush()
            logger.info(f"  ✅ Source créée : {source.code}")
        else:
            logger.info(f"  ✓  Source existante : {source.code}")
        return source

    # ── Permissions ───────────────────────────────────────────────

    async def _load_permissions(
        self, source: PermissionSource
    ) -> tuple[int, int]:
        crees = exist = 0
        for pdata in self.data.get("permissions", []):
            code   = pdata["code"]
            result = await self.db.execute(
                select(Permission).where(Permission.code == code)
            )
            perm = result.scalar_one_or_none()
            if not perm:
                perm = Permission(
                    source_id         = source.id,
                    code              = code,
                    nom               = pdata["nom"],
                    domaine           = pdata["domaine"],
                    ressource         = pdata["ressource"],
                    action            = pdata["action"],
                    actif             = True,
                    necessite_perimetre = pdata.get("necessite_perimetre", False),
                    deprecated        = False,
                )
                self.db.add(perm)
                await self.db.flush()
                crees += 1
            else:
                exist += 1
            self._perms_map[code] = perm

        return crees, exist

    # ── Rôles ─────────────────────────────────────────────────────

    async def _load_roles(self) -> tuple[int, int]:
        crees = exist = 0
        all_perm_codes = list(self._perms_map.keys())

        for rdata in self.data.get("roles", []):
            code   = rdata["code"]
            result = await self.db.execute(
                select(Role).where(Role.code == code)
            )
            role = result.scalar_one_or_none()
            if not role:
                role = Role(
                    code      = code,
                    nom       = rdata["nom"],
                    description = rdata.get("description", ""),
                    type_role = rdata.get("type_role", "fonctionnel"),
                    actif     = True,
                    systeme   = rdata.get("systeme", False),
                )
                self.db.add(role)
                await self.db.flush()
                crees += 1

                # Résoudre les permissions
                perm_codes = (
                    all_perm_codes
                    if rdata.get("permissions") == "$ALL"
                    else rdata.get("permissions", [])
                )
                for pcode in perm_codes:
                    if pcode in self._perms_map:
                        await self.db.execute(
                            insert(role_permissions_table).values(
                                role_id       = role.id,
                                permission_id = self._perms_map[pcode].id,
                            )
                        )
            else:
                exist += 1
            self._roles_map[code] = role

        return crees, exist

    # ── Groupes ───────────────────────────────────────────────────

    async def _load_groupes(self) -> tuple[int, int]:
        crees = exist = 0
        for gdata in self.data.get("groupes", []):
            code   = gdata["code"]
            result = await self.db.execute(
                select(Groupe).where(Groupe.code == code)
            )
            groupe = result.scalar_one_or_none()
            if not groupe:
                groupe = Groupe(
                    code        = code,
                    nom         = gdata["nom"],
                    description = gdata.get("description", ""),
                    type_groupe = gdata.get("type_groupe", "fonctionnel"),
                    actif       = True,
                    systeme     = gdata.get("systeme", False),
                )
                self.db.add(groupe)
                await self.db.flush()

                # Lier les rôles
                for rcode in gdata.get("roles", []):
                    if rcode in self._roles_map:
                        grp_role = GroupeRole(
                            groupe_id = groupe.id,
                            role_id   = self._roles_map[rcode].id,
                        )
                        self.db.add(grp_role)
                crees += 1
            else:
                exist += 1
            self._groupes_map[code] = groupe

        return crees, exist

    # ── Endpoints ─────────────────────────────────────────────────

    async def _load_endpoints(
        self, source: PermissionSource
    ) -> tuple[int, int]:
        """
        Charge les endpoints depuis le JSON.
        Résout les codes de permissions en UUID[] avant insertion.
        Contrainte unique : (source_id, path, method).
        """
        crees = exist = 0
        for epdata in self.data.get("endpoints", []):
            path   = epdata["path"]
            method = epdata["method"].upper()

            # Vérifier existence
            result = await self.db.execute(
                select(EndpointPermission).where(
                    EndpointPermission.source_id == source.id,
                    EndpointPermission.path      == path,
                    EndpointPermission.method    == method,
                    EndpointPermission.is_deleted == False,
                )
            )
            ep = result.scalar_one_or_none()
            if ep:
                exist += 1
                continue

            # Résoudre les codes de permissions en UUIDs
            perm_uuids = []
            for pcode in epdata.get("permissions", []):
                if pcode in self._perms_map:
                    perm_uuids.append(self._perms_map[pcode].id)
                else:
                    logger.warning(
                        f"  ⚠️  Permission inconnue '{pcode}' "
                        f"pour endpoint {method} {path}"
                    )

            ep = EndpointPermission(
                source_id       = source.id,
                path            = path,
                method          = method,
                permission_uuids= perm_uuids,
                description     = epdata.get("description", ""),
                public          = epdata.get("public", False),
                actif           = True,
            )
            self.db.add(ep)
            crees += 1

        await self.db.flush()
        return crees, exist
