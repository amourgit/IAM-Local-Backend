"""
Service d'enregistrement des endpoints depuis les modules externes.
Reçoit les endpoints via Kafka topic: iam.registration.endpoints
"""

import logging
from typing import Dict, Any, List
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db_session
from app.repositories.endpoint_permission import EndpointPermissionRepository
from app.repositories.permission import PermissionRepository, PermissionSourceRepository
from app.core.exceptions import ValidationError

logger = logging.getLogger(__name__)

METHODES_VALIDES = {"GET", "POST", "PUT", "PATCH", "DELETE", "HEAD", "OPTIONS"}


class EndpointRegistrationService:
    """
    Gère l'enregistrement des endpoints publiés par les modules externes.
    Mappe chaque (path + method) à une liste de permissions requises.
    """

    async def handle_registration(self, payload: Dict[str, Any]) -> None:
        """
        Traite un message de registration d'endpoints.

        Payload attendu :
        {
            "source_code": "scolarite",
            "source_nom":  "Module Scolarité",
            "version": "1.0",
            "endpoints": [
                {
                    "path": "/api/v1/inscriptions",
                    "method": "POST",
                    "permission_codes": ["scolarite.inscription.creer"],
                    "description": "Soumettre une inscription",
                    "public": false
                }
            ]
        }
        """
        source_code = payload.get("source_code")
        source_nom  = payload.get("source_nom")
        version     = payload.get("version", "1.0")
        endpoints   = payload.get("endpoints", [])

        if not source_code:
            logger.error("Endpoint registration: source_code manquant")
            return

        if not endpoints:
            logger.warning(f"Endpoint registration: aucun endpoint pour {source_code}")
            return

        logger.info(
            f"Enregistrement endpoints: source={source_code} "
            f"version={version} count={len(endpoints)}"
        )

        db = await get_db_session()
        try:
            await self._upsert_endpoints(
                db          = db,
                source_code = source_code,
                source_nom  = source_nom or source_code,
                endpoints   = endpoints,
            )
            await db.commit()
            logger.info(
                f"✅ {len(endpoints)} endpoints enregistrés "
                f"pour source={source_code}"
            )
        except Exception as e:
            await db.rollback()
            logger.error(
                f"Erreur enregistrement endpoints pour {source_code}: {e}",
                exc_info=True
            )
        finally:
            await db.close()

    async def _upsert_endpoints(
        self,
        db          : AsyncSession,
        source_code : str,
        source_nom  : str,
        endpoints   : list,
    ) -> None:
        src_repo  = PermissionSourceRepository(db)
        perm_repo = PermissionRepository(db)
        ep_repo   = EndpointPermissionRepository(db)

        # ── 1. Récupérer la source (doit exister) ────────────────
        source = await src_repo.get_by_code(source_code)
        if not source:
            # Créer la source si inexistante
            # (peut arriver si endpoints arrivent avant permissions)
            source = await src_repo.create({
                "code"        : source_code,
                "nom"         : source_nom,
                "description" : f"Module {source_nom} — enregistré via Kafka",
                "actif"       : True,
            })
            logger.warning(
                f"Source {source_code} créée à la volée "
                f"(les permissions devraient arriver séparément)"
            )

        # ── 2. Upsert chaque endpoint ─────────────────────────────
        created_count = 0
        updated_count = 0
        skipped_count = 0

        for ep_data in endpoints:
            path   = ep_data.get("path", "").strip()
            method = ep_data.get("method", "").upper().strip()

            # Validations basiques
            if not path or not path.startswith("/"):
                logger.warning(f"Endpoint path invalide ignoré: {path}")
                skipped_count += 1
                continue

            if method not in METHODES_VALIDES:
                logger.warning(f"Méthode HTTP invalide ignorée: {method}")
                skipped_count += 1
                continue

            permission_codes = ep_data.get("permission_codes", [])
            public           = ep_data.get("public", False)
            description      = ep_data.get("description", "")

            # ── Résoudre les codes de permissions en UUIDs ────────
            permission_uuids = await self._resolve_permission_uuids(
                perm_repo        = perm_repo,
                permission_codes = permission_codes,
                source_code      = source_code,
                path             = path,
                method           = method,
            )

            # Un endpoint non-public doit avoir au moins 1 permission
            if not public and not permission_uuids:
                logger.warning(
                    f"Endpoint {method} {path} ignoré: "
                    f"aucune permission résolue et non-public"
                )
                skipped_count += 1
                continue

            # ── Upsert ────────────────────────────────────────────
            existing = await ep_repo.get_by_path_method(
                source_id = source.id,
                path      = path,
                method    = method,
            )

            if existing:
                await ep_repo.update(existing.id, {
                    "permission_uuids" : permission_uuids,
                    "description"      : description or existing.description,
                    "public"           : public,
                    "actif"            : True,
                })
                updated_count += 1
            else:
                await ep_repo.create({
                    "source_id"        : source.id,
                    "path"             : path,
                    "method"           : method,
                    "permission_uuids" : permission_uuids,
                    "description"      : description,
                    "public"           : public,
                    "actif"            : True,
                })
                created_count += 1

        logger.info(
            f"Source={source_code}: "
            f"{created_count} endpoints créés, "
            f"{updated_count} mis à jour, "
            f"{skipped_count} ignorés"
        )

    async def _resolve_permission_uuids(
        self,
        perm_repo        : PermissionRepository,
        permission_codes : List[str],
        source_code      : str,
        path             : str,
        method           : str,
    ) -> List:
        """
        Résout les codes de permissions en UUIDs.
        Log un warning pour les codes non trouvés.
        """
        uuids = []
        for code in permission_codes:
            perm = await perm_repo.get_by_code(code)
            if perm:
                uuids.append(perm.id)
            else:
                logger.warning(
                    f"Permission '{code}' non trouvée pour "
                    f"{method} {path} (source={source_code}) — "
                    f"publier d'abord les permissions via "
                    f"iam.registration.permissions"
                )
        return uuids
