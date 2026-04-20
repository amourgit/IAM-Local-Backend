"""
SeedLoader — Synchronisation des données de référence depuis seeds/data/iam_seed.json.

PRINCIPE FONDAMENTAL (strictement additif) :
  - Ce qui est dans le JSON mais PAS en DB  → on insère
  - Ce qui est en DB mais PAS dans le JSON  → on ne touche PAS
    (c'est une donnée créée via les APIs, elle appartient au métier)

Exécuté à chaque démarrage du serveur pour synchroniser automatiquement
les nouvelles données ajoutées dans iam_seed.json.

Gestion d'erreur robuste : une erreur dans le chargement n'arrête PAS
le serveur — elle est loggée et le serveur continue.
"""
import json
import logging
from pathlib import Path
from typing import Dict, Any, List, Optional, Tuple
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, insert
from sqlalchemy.exc import IntegrityError

from app.models.permission_source import PermissionSource
from app.models.permission import Permission
from app.models.role import Role, role_permissions_table
from app.models.groupe import Groupe, GroupeRole
from app.models.endpoint_permission import EndpointPermission

logger    = logging.getLogger(__name__)
SEED_FILE = Path(__file__).parent / "data" / "iam_seed.json"


def _load_json_safe() -> Optional[Dict[str, Any]]:
    """
    Charge iam_seed.json avec validation basique.
    Retourne None en cas d'erreur (fichier absent, JSON invalide, structure manquante).
    Ne plante JAMAIS.
    """
    try:
        if not SEED_FILE.exists():
            logger.warning(f"SeedLoader: fichier introuvable — {SEED_FILE}")
            return None

        raw = SEED_FILE.read_text(encoding="utf-8")
        data = json.loads(raw)

        # Validation structure minimale
        required_keys = {"source", "permissions", "roles", "groupes", "endpoints"}
        missing = required_keys - set(data.keys())
        if missing:
            logger.error(
                f"SeedLoader: clés manquantes dans iam_seed.json — {missing}. "
                "Chargement annulé."
            )
            return None

        # Validation source
        src = data.get("source", {})
        if not src.get("code") or not src.get("nom"):
            logger.error("SeedLoader: source.code et source.nom sont obligatoires.")
            return None

        return data

    except json.JSONDecodeError as e:
        logger.error(
            f"SeedLoader: JSON invalide dans iam_seed.json — {e}. "
            "Chargement annulé. Corrigez le fichier et redémarrez."
        )
        return None
    except Exception as e:
        logger.error(f"SeedLoader: erreur lecture iam_seed.json — {e}")
        return None


class SeedLoader:
    """
    Synchronise les données de référence natives (iam_seed.json) vers la DB.

    Strictement additif :
    ✅ JSON présent, DB absente  → INSERT
    ✅ JSON présent, DB présente → SKIP (idempotent)
    ❌ JSON absent, DB présente  → SKIP (on ne supprime rien)

    Robuste : chaque section est indépendante — une erreur partielle
    ne bloque pas les autres sections.
    """

    def __init__(self, db: AsyncSession):
        self.db          = db
        self.data        : Optional[Dict[str, Any]] = None
        self._perms_map  : Dict[str, Permission]    = {}
        self._roles_map  : Dict[str, Role]          = {}
        self._source     : Optional[PermissionSource] = None

    async def run(self) -> Dict[str, Any]:
        """
        Point d'entrée principal.
        Retourne un rapport même en cas d'erreurs partielles.
        Ne lève JAMAIS d'exception — toutes les erreurs sont loggées.
        """
        rapport = {
            "ok"         : False,
            "source"     : None,
            "permissions": {"ajoutees": 0, "existantes": 0, "erreurs": 0},
            "roles"      : {"ajoutes": 0, "existants": 0, "erreurs": 0},
            "groupes"    : {"ajoutes": 0, "existants": 0, "erreurs": 0},
            "endpoints"  : {"ajoutes": 0, "existants": 0, "erreurs": 0},
            "erreurs"    : [],
        }

        # Charger le JSON — si invalide, arrêt propre sans exception
        self.data = _load_json_safe()
        if self.data is None:
            rapport["erreurs"].append("JSON invalide ou introuvable — aucune synchronisation")
            return rapport

        logger.info("SeedLoader: démarrage synchronisation iam_seed.json → DB")

        # ── Source ────────────────────────────────────────────────
        try:
            self._source = await self._sync_source()
            rapport["source"] = self._source.code if self._source else None
        except Exception as e:
            err = f"Source: {e}"
            logger.error(f"SeedLoader: {err}")
            rapport["erreurs"].append(err)
            return rapport  # Sans source, on ne peut pas continuer

        # ── Permissions ───────────────────────────────────────────
        try:
            a, e, er = await self._sync_permissions()
            rapport["permissions"] = {"ajoutees": a, "existantes": e, "erreurs": er}
        except Exception as e:
            err = f"Permissions: {e}"
            logger.error(f"SeedLoader: {err}")
            rapport["erreurs"].append(err)

        # ── Rôles ─────────────────────────────────────────────────
        try:
            a, e, er = await self._sync_roles()
            rapport["roles"] = {"ajoutes": a, "existants": e, "erreurs": er}
        except Exception as e:
            err = f"Rôles: {e}"
            logger.error(f"SeedLoader: {err}")
            rapport["erreurs"].append(err)

        # ── Groupes ───────────────────────────────────────────────
        try:
            a, e, er = await self._sync_groupes()
            rapport["groupes"] = {"ajoutes": a, "existants": e, "erreurs": er}
        except Exception as e:
            err = f"Groupes: {e}"
            logger.error(f"SeedLoader: {err}")
            rapport["erreurs"].append(err)

        # ── Endpoints ─────────────────────────────────────────────
        try:
            a, e, er = await self._sync_endpoints()
            rapport["endpoints"] = {"ajoutes": a, "existants": e, "erreurs": er}
        except Exception as e:
            err = f"Endpoints: {e}"
            logger.error(f"SeedLoader: {err}")
            rapport["erreurs"].append(err)

        # Mettre à jour nb_permissions
        try:
            if self._source:
                self._source.nb_permissions = len(self._perms_map)
                self.db.add(self._source)
                await self.db.flush()
        except Exception:
            pass

        rapport["ok"] = len(rapport["erreurs"]) == 0

        total_new = (
            rapport["permissions"]["ajoutees"]
            + rapport["roles"]["ajoutes"]
            + rapport["groupes"]["ajoutes"]
            + rapport["endpoints"]["ajoutes"]
        )

        if total_new > 0:
            logger.info(
                f"SeedLoader ✅ : +{rapport['permissions']['ajoutees']} perms "
                f"| +{rapport['roles']['ajoutes']} rôles "
                f"| +{rapport['groupes']['ajoutes']} groupes "
                f"| +{rapport['endpoints']['ajoutes']} endpoints"
            )
        else:
            logger.info("SeedLoader ✅ : tout est à jour, rien à synchroniser")

        if rapport["erreurs"]:
            logger.warning(f"SeedLoader ⚠️  : {len(rapport['erreurs'])} erreur(s) — {rapport['erreurs']}")

        return rapport

    # ── Source ────────────────────────────────────────────────────

    async def _sync_source(self) -> PermissionSource:
        src_data = self.data["source"]
        result   = await self.db.execute(
            select(PermissionSource).where(PermissionSource.code == src_data["code"])
        )
        source = result.scalar_one_or_none()
        if not source:
            source = PermissionSource(
                code          = src_data["code"],
                nom           = src_data["nom"],
                description   = src_data.get("description", ""),
                version       = src_data.get("version", "1.0.0"),
                actif         = True,
                nb_permissions= 0,
            )
            self.db.add(source)
            await self.db.flush()
            logger.info(f"  ✅ Source créée : {source.code}")
        return source

    # ── Permissions ───────────────────────────────────────────────

    async def _sync_permissions(self) -> Tuple[int, int, int]:
        """Retourne (ajoutees, existantes, erreurs)."""
        # Charger toutes les permissions existantes en une requête
        result = await self.db.execute(select(Permission))
        existing = {p.code: p for p in result.scalars().all()}

        ajoutees = existantes = erreurs = 0

        for pdata in self.data.get("permissions", []):
            code = pdata.get("code", "")
            if not code:
                erreurs += 1
                continue

            if code in existing:
                self._perms_map[code] = existing[code]
                existantes += 1
                continue

            # Validation minimale
            required = {"code", "nom", "domaine", "ressource", "action"}
            missing  = required - set(pdata.keys())
            if missing:
                logger.warning(f"  ⚠️  Permission {code} — champs manquants: {missing}")
                erreurs += 1
                continue

            try:
                perm = Permission(
                    source_id           = self._source.id,
                    code                = code,
                    nom                 = pdata["nom"],
                    domaine             = pdata["domaine"],
                    ressource           = pdata["ressource"],
                    action              = pdata["action"],
                    actif               = True,
                    necessite_perimetre = pdata.get("necessite_perimetre", False),
                    deprecated          = False,
                )
                self.db.add(perm)
                await self.db.flush()
                self._perms_map[code] = perm
                existing[code]        = perm
                ajoutees += 1
                logger.debug(f"  + Permission ajoutée : {code}")
            except Exception as e:
                logger.warning(f"  ⚠️  Permission {code} — erreur: {e}")
                await self.db.rollback()
                erreurs += 1

        # Charger aussi les permissions existantes en DB qui ne sont pas dans le JSON
        # (créées via API) — on les met dans la map pour la résolution des rôles
        for code, perm in existing.items():
            if code not in self._perms_map:
                self._perms_map[code] = perm

        return ajoutees, existantes, erreurs

    # ── Rôles ─────────────────────────────────────────────────────

    async def _sync_roles(self) -> Tuple[int, int, int]:
        """Retourne (ajoutes, existants, erreurs). Strictement additif."""
        # Charger tous les rôles existants
        result = await self.db.execute(select(Role))
        existing = {r.code: r for r in result.scalars().all()}

        # Charger les associations rôle-permission existantes
        rp_result = await self.db.execute(
            select(role_permissions_table)
        )
        existing_rp = set(
            (str(row.role_id), str(row.permission_id))
            for row in rp_result
        )

        all_perm_codes = list(self._perms_map.keys())
        ajoutes = existants = erreurs = 0

        for rdata in self.data.get("roles", []):
            code = rdata.get("code", "")
            if not code:
                erreurs += 1
                continue

            if code in existing:
                role = existing[code]
                self._roles_map[code] = role
                existants += 1

                # Ajouter les permissions manquantes (additif uniquement)
                perm_codes = (
                    all_perm_codes
                    if rdata.get("permissions") == "$ALL"
                    else rdata.get("permissions", [])
                )
                for pcode in perm_codes:
                    if pcode not in self._perms_map:
                        continue
                    perm = self._perms_map[pcode]
                    key  = (str(role.id), str(perm.id))
                    if key not in existing_rp:
                        try:
                            await self.db.execute(
                                insert(role_permissions_table).values(
                                    role_id=role.id, permission_id=perm.id
                                )
                            )
                            existing_rp.add(key)
                            logger.debug(f"  + Permission {pcode} ajoutée au rôle {code}")
                        except IntegrityError:
                            await self.db.rollback()
                continue

            # Rôle inexistant → créer
            required = {"code", "nom"}
            missing  = required - set(rdata.keys())
            if missing:
                logger.warning(f"  ⚠️  Rôle {code} — champs manquants: {missing}")
                erreurs += 1
                continue

            try:
                role = Role(
                    code        = code,
                    nom         = rdata["nom"],
                    description = rdata.get("description", ""),
                    type_role   = rdata.get("type_role", "fonctionnel"),
                    actif       = True,
                    systeme     = rdata.get("systeme", False),
                )
                self.db.add(role)
                await self.db.flush()

                perm_codes = (
                    all_perm_codes
                    if rdata.get("permissions") == "$ALL"
                    else rdata.get("permissions", [])
                )
                for pcode in perm_codes:
                    if pcode in self._perms_map:
                        await self.db.execute(
                            insert(role_permissions_table).values(
                                role_id=role.id,
                                permission_id=self._perms_map[pcode].id,
                            )
                        )

                self._roles_map[code] = role
                existing[code]        = role
                ajoutes += 1
                logger.debug(f"  + Rôle ajouté : {code}")
            except Exception as e:
                logger.warning(f"  ⚠️  Rôle {code} — erreur: {e}")
                await self.db.rollback()
                erreurs += 1

        # Charger aussi les rôles DB hors JSON dans la map
        for code, role in existing.items():
            if code not in self._roles_map:
                self._roles_map[code] = role

        return ajoutes, existants, erreurs

    # ── Groupes ───────────────────────────────────────────────────

    async def _sync_groupes(self) -> Tuple[int, int, int]:
        result   = await self.db.execute(select(Groupe))
        existing = {g.code: g for g in result.scalars().all()}

        ajoutes = existants = erreurs = 0

        for gdata in self.data.get("groupes", []):
            code = gdata.get("code", "")
            if not code:
                erreurs += 1
                continue

            if code in existing:
                existants += 1
                continue

            try:
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

                for rcode in gdata.get("roles", []):
                    if rcode in self._roles_map:
                        grp_role = GroupeRole(
                            groupe_id = groupe.id,
                            role_id   = self._roles_map[rcode].id,
                        )
                        self.db.add(grp_role)

                existing[code] = groupe
                ajoutes += 1
                logger.debug(f"  + Groupe ajouté : {code}")
            except Exception as e:
                logger.warning(f"  ⚠️  Groupe {code} — erreur: {e}")
                await self.db.rollback()
                erreurs += 1

        return ajoutes, existants, erreurs

    # ── Endpoints ─────────────────────────────────────────────────

    async def _sync_endpoints(self) -> Tuple[int, int, int]:
        """
        Charge les endpoints de façon additive.
        Clé d'unicité : (source_id, path, method).
        """
        # Charger tous les endpoints existants pour cette source
        result = await self.db.execute(
            select(EndpointPermission).where(
                EndpointPermission.source_id  == self._source.id,
                EndpointPermission.is_deleted == False,
            )
        )
        existing = {
            (ep.path, ep.method): ep
            for ep in result.scalars().all()
        }

        ajoutes = existants = erreurs = 0

        for epdata in self.data.get("endpoints", []):
            path   = epdata.get("path", "")
            method = epdata.get("method", "").upper()

            if not path or not method:
                logger.warning(f"  ⚠️  Endpoint invalide: {epdata}")
                erreurs += 1
                continue

            if (path, method) in existing:
                existants += 1
                continue

            # Résoudre les codes permissions → UUIDs
            perm_uuids = []
            for pcode in epdata.get("permissions", []):
                if pcode in self._perms_map:
                    perm_uuids.append(self._perms_map[pcode].id)
                else:
                    logger.warning(
                        f"  ⚠️  Permission inconnue '{pcode}' "
                        f"pour {method} {path} — ignorée"
                    )

            try:
                ep = EndpointPermission(
                    source_id        = self._source.id,
                    path             = path,
                    method           = method,
                    permission_uuids = perm_uuids,
                    description      = epdata.get("description", ""),
                    public           = epdata.get("public", False),
                    actif            = True,
                )
                self.db.add(ep)
                existing[(path, method)] = ep
                ajoutes += 1
                logger.debug(f"  + Endpoint ajouté : {method} {path}")
            except Exception as e:
                logger.warning(f"  ⚠️  Endpoint {method} {path} — erreur: {e}")
                erreurs += 1

        try:
            await self.db.flush()
        except Exception as e:
            logger.error(f"SeedLoader: flush endpoints échoué — {e}")
            await self.db.rollback()
            erreurs += ajoutes
            ajoutes = 0

        return ajoutes, existants, erreurs
