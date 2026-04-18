"""
Service d'enregistrement des permissions depuis les modules externes.
Reçoit les permissions via Kafka topic: iam.registration.permissions
"""

import logging
from typing import Dict, Any
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db_session
from app.repositories.permission import PermissionRepository, PermissionSourceRepository
from app.core.exceptions import ValidationError

logger = logging.getLogger(__name__)


class PermissionRegistrationService:
    """
    Gère l'enregistrement des permissions publiées par les modules externes.
    Crée ou met à jour la PermissionSource et ses permissions associées.
    """

    async def handle_registration(self, payload: Dict[str, Any]) -> None:
        """
        Traite un message de registration de permissions.

        Payload attendu :
        {
            "source_code": "scolarite",
            "source_nom": "Module Scolarité",
            "version": "1.0",
            "permissions": [
                {
                    "code": "scolarite.inscription.creer",
                    "libelle": "Créer une inscription",
                    "domaine": "scolarite",
                    "ressource": "inscription",
                    "action": "creer"
                }
            ]
        }
        """
        source_code = payload.get("source_code")
        source_nom  = payload.get("source_nom")
        version     = payload.get("version", "1.0")
        permissions = payload.get("permissions", [])

        if not source_code:
            logger.error("Permission registration: source_code manquant")
            return

        if not permissions:
            logger.warning(f"Permission registration: aucune permission pour {source_code}")
            return

        logger.info(
            f"Enregistrement permissions: source={source_code} "
            f"version={version} count={len(permissions)}"
        )

        db = await get_db_session()
        try:
            await self._upsert_source_and_permissions(
                db          = db,
                source_code = source_code,
                source_nom  = source_nom or source_code,
                version     = version,
                permissions = permissions,
            )
            await db.commit()
            logger.info(
                f"✅ {len(permissions)} permissions enregistrées "
                f"pour source={source_code}"
            )
        except Exception as e:
            await db.rollback()
            logger.error(
                f"Erreur enregistrement permissions pour {source_code}: {e}",
                exc_info=True
            )
        finally:
            await db.close()

    async def _upsert_source_and_permissions(
        self,
        db          : AsyncSession,
        source_code : str,
        source_nom  : str,
        version     : str,
        permissions : list,
    ) -> None:
        src_repo  = PermissionSourceRepository(db)
        perm_repo = PermissionRepository(db)

        # ── 1. Créer ou récupérer la source ──────────────────────
        source = await src_repo.get_by_code(source_code)
        if not source:
            source = await src_repo.create({
                "code"        : source_code,
                "nom"         : source_nom,
                "description" : f"Module {source_nom} — enregistré via Kafka",
                "actif"       : True,
            })
            logger.info(f"Source créée: {source_code}")
        else:
            # Mettre à jour le nom si changé
            if source.nom != source_nom:
                await src_repo.update(source.id, {"nom": source_nom})
            logger.info(f"Source existante: {source_code} (id={source.id})")

        # ── 2. Upsert chaque permission ───────────────────────────
        created_count = 0
        updated_count = 0

        for perm_data in permissions:
            code = perm_data.get("code")
            if not code:
                logger.warning(f"Permission sans code ignorée: {perm_data}")
                continue

            # Valider le format code: domaine.ressource.action
            parts = code.split(".")
            if len(parts) < 3:
                logger.warning(f"Format de code invalide: {code}")
                continue

            existing = await perm_repo.get_by_code(code)

            if existing:
                # Mettre à jour si nécessaire
                await perm_repo.update(existing.id, {
                    "libelle"     : perm_data.get("libelle", existing.libelle),
                    "description" : perm_data.get("description", existing.description),
                })
                updated_count += 1
            else:
                # Créer nouvelle permission
                await perm_repo.create({
                    "source_id"   : source.id,
                    "code"        : code,
                    "libelle"     : perm_data.get("libelle", code),
                    "description" : perm_data.get("description", ""),
                    "domaine"     : perm_data.get("domaine", parts[0]),
                    "ressource"   : perm_data.get("ressource", parts[1]),
                    "action"      : perm_data.get("action", ".".join(parts[2:])),
                    "actif"       : True,
                })
                created_count += 1

        logger.info(
            f"Source={source_code}: "
            f"{created_count} permissions créées, "
            f"{updated_count} mises à jour"
        )
