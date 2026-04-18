"""
Service de nettoyage automatique du profil bootstrap.

Déclenché automatiquement quand un administrateur réel
(rôle iam.admin) se connecte avec succès pour la première fois.

Supprime proprement :
  - Profil bootstrap (soft delete)
  - Assignation du rôle iam.admin_temp (soft delete)
  - Token blacklisté dans Redis
  - Fichier credentials.json supprimé

Préserve intégralement :
  - Tous les logs journal_acces (immuables)
  - Les permissions et rôles (réutilisables)
  - L'historique complet des actions bootstrap
"""
import logging
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional
from uuid import UUID

from sqlalchemy import select, and_
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.bootstrap_config import (
    BOOTSTRAP_IDENTIFIANT,
    BOOTSTRAP_STATUT,
    ROLE_TEMP_CODE,
)

logger = logging.getLogger(__name__)
CREDENTIALS_FILE = Path("bootstrap_credentials.json")


class BootstrapCleanupService:
    """
    Nettoyage automatique sécurisé du profil bootstrap.
    Appelé dès qu'un admin réel se connecte avec succès.
    """

    def __init__(self, db: AsyncSession):
        self.db = db

    async def verifier_et_nettoyer(
        self,
        profil_connecte_id : UUID,
        profil_connecte_roles : list[str],
    ) -> bool:
        """
        Point d'entrée principal.

        Appelé à chaque connexion réussie.
        Vérifie si :
          1. Le profil connecté est un admin réel (rôle iam.admin)
          2. Il existe encore un profil bootstrap actif

        Si les deux conditions sont vraies → nettoyage complet.

        Retourne True si nettoyage effectué, False sinon.
        """
        # Condition 1 : le profil connecté est un vrai admin
        if ROLE_TEMP_CODE in profil_connecte_roles:
            # C'est le bootstrap lui-même qui se connecte — pas de nettoyage
            return False

        if "iam.admin" not in profil_connecte_roles:
            # Pas un admin → pas de nettoyage
            return False

        # Condition 2 : un profil bootstrap existe encore
        profil_bootstrap = await self._get_profil_bootstrap()
        if not profil_bootstrap:
            # Déjà nettoyé
            return False

        # Les deux conditions sont vraies → nettoyage
        logger.warning(
            f"🔐 Admin réel détecté ({profil_connecte_id}). "
            "Nettoyage automatique du profil bootstrap en cours..."
        )

        await self._nettoyer_profil_bootstrap(
            profil_bootstrap   = profil_bootstrap,
            supprime_par       = profil_connecte_id,
        )

        logger.warning(
            "✅ Profil bootstrap supprimé proprement. "
            "Traçabilité complète préservée dans journal_acces."
        )
        return True

    async def _get_profil_bootstrap(self):
        """Recherche le profil bootstrap encore actif."""
        from app.models.compte_local import CompteLocal
        from app.models.profil_local import ProfilLocal

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

    async def _nettoyer_profil_bootstrap(
        self,
        profil_bootstrap,
        supprime_par : UUID,
    ) -> None:
        """
        Nettoyage complet en 4 étapes.
        Tout est soft delete — rien n'est détruit physiquement.
        """
        now = datetime.now(timezone.utc)

        # ── Étape 1 : Révoquer toutes les assignations de rôles ──
        await self._revoquer_assignations(
            profil_bootstrap.id, supprime_par, now
        )

        # ── Étape 2 : Retirer de tous les groupes ────────────────
        await self._retirer_des_groupes(
            profil_bootstrap.id, supprime_par, now
        )

        # ── Étape 3 : Invalider le token dans Redis ───────────────
        await self._invalider_token_redis(profil_bootstrap.id)

        # ── Étape 4 : Soft delete du profil ──────────────────────
        profil_bootstrap.is_deleted  = True
        profil_bootstrap.deleted_at  = now
        profil_bootstrap.deleted_by  = supprime_par
        profil_bootstrap.statut      = "inactif"
        # Désactiver aussi le CompteLocal bootstrap
        if hasattr(profil_bootstrap, "compte") and profil_bootstrap.compte:
            profil_bootstrap.compte.is_deleted = True
            profil_bootstrap.compte.deleted_at = now
            profil_bootstrap.compte.deleted_by = supprime_par
            profil_bootstrap.compte.statut     = "inactif"
            self.db.add(profil_bootstrap.compte)
        profil_bootstrap.notes       = (
            f"Profil bootstrap supprimé automatiquement le "
            f"{now.isoformat()} par admin réel {supprime_par}. "
            "Suppression déclenchée à la première connexion admin réel."
        )
        self.db.add(profil_bootstrap)

        # ── Étape 5 : Log audit (immuable) ────────────────────────
        await self._log_audit_suppression(
            profil_bootstrap.id, supprime_par, now
        )

        # ── Étape 6 : Supprimer credentials.json ─────────────────
        self._supprimer_credentials_file()

        # ── Étape 7 : Invalider cache habilitations ───────────────
        await self._invalider_cache_habilitations(profil_bootstrap.id)

        await self.db.flush()

    async def _revoquer_assignations(
        self,
        profil_id    : UUID,
        supprime_par : UUID,
        now          : datetime,
    ) -> None:
        """Révoque toutes les assignations de rôles du profil bootstrap."""
        from app.models.assignation_role import AssignationRole

        result = await self.db.execute(
            select(AssignationRole).where(
                and_(
                    AssignationRole.profil_id  == profil_id,
                    AssignationRole.is_deleted == False,
                )
            )
        )
        assignations = result.scalars().all()

        for assignation in assignations:
            assignation.statut             = "revoquee"
            assignation.is_deleted         = True
            assignation.deleted_at         = now
            assignation.deleted_by         = supprime_par
            assignation.raison_revocation  = (
                "Révocation automatique — suppression profil bootstrap"
            )
            self.db.add(assignation)

        logger.info(
            f"   ✓ {len(assignations)} assignation(s) révoquée(s)"
        )

    async def _retirer_des_groupes(
        self,
        profil_id    : UUID,
        supprime_par : UUID,
        now          : datetime,
    ) -> None:
        """Retire le profil bootstrap de tous les groupes."""
        from app.models.assignation_groupe import AssignationGroupe

        result = await self.db.execute(
            select(AssignationGroupe).where(
                and_(
                    AssignationGroupe.profil_id  == profil_id,
                    AssignationGroupe.is_deleted == False,
                )
            )
        )
        assignations = result.scalars().all()

        for assignation in assignations:
            assignation.is_deleted  = True
            assignation.deleted_at  = now
            assignation.deleted_by  = supprime_par
            self.db.add(assignation)

        if assignations:
            logger.info(
                f"   ✓ {len(assignations)} appartenance(s) groupe révoquée(s)"
            )

    async def _invalider_token_redis(self, profil_id: UUID) -> None:
        """
        Invalide tous les tokens du profil bootstrap dans Redis.
        Blacklist par profil_id — tout token avec ce sub est rejeté.
        """
        try:
            from app.infrastructure.cache.redis import CacheService
            cache = CacheService()

            # Blacklist le profil_id — vérifié à chaque requête auth
            blacklist_key = f"iam:blacklist:profil:{profil_id}"
            await cache.set(
                key   = blacklist_key,
                value = {
                    "blacklisted"  : True,
                    "raison"       : "bootstrap_cleanup",
                    "profil_id"    : str(profil_id),
                },
                ttl   = 172800,  # 48h = durée max du token bootstrap
            )
            logger.info(
                f"   ✓ Token blacklisté dans Redis : {blacklist_key}"
            )
        except Exception as e:
            logger.error(f"Redis blacklist error (non bloquant) : {e}")

    async def _log_audit_suppression(
        self,
        profil_bootstrap_id : UUID,
        supprime_par        : UUID,
        now                 : datetime,
    ) -> None:
        """
        Crée une entrée immuable dans journal_acces.
        Cette entrée ne peut jamais être supprimée.
        """
        try:
            from app.models.journal_acces import JournalAcces

            log = JournalAcces(
                profil_id         = profil_bootstrap_id,
                user_id_national  = None,
                type_action       = "bootstrap_cleanup",
                module            = "iam-local",
                ressource         = "profil_bootstrap",
                ressource_id      = str(profil_bootstrap_id),
                autorise          = True,
                details           = {
                    "action"       : "suppression_automatique_bootstrap",
                    "supprime_par" : str(supprime_par),
                    "timestamp"    : now.isoformat(),
                    "raison"       : (
                        "Suppression automatique déclenchée par la "
                        "première connexion d'un administrateur réel."
                    ),
                    "traçabilite"  : (
                        "Toutes les actions bootstrap sont préservées "
                        "dans ce journal pour audit complet."
                    ),
                },
                ip_address        = "system",
                timestamp         = now,
            )
            self.db.add(log)
            logger.info("   ✓ Log audit suppression créé (immuable)")
        except Exception as e:
            logger.error(f"Audit log error (non bloquant) : {e}")

    def _supprimer_credentials_file(self) -> None:
        """Supprime le fichier credentials.json s'il existe."""
        try:
            if CREDENTIALS_FILE.exists():
                CREDENTIALS_FILE.unlink()
                logger.info(
                    "   ✓ bootstrap_credentials.json supprimé"
                )
            else:
                logger.debug(
                    "   → bootstrap_credentials.json déjà absent"
                )
        except Exception as e:
            logger.warning(
                f"Impossible de supprimer credentials.json : {e}. "
                "Supprimez-le manuellement."
            )

    async def _invalider_cache_habilitations(
        self, profil_id: UUID
    ) -> None:
        """Invalide le cache Redis des habilitations du bootstrap."""
        try:
            from app.infrastructure.cache.redis import CacheService
            cache = CacheService()
            await cache.delete(
                f"iam:habilitations:{profil_id}"
            )
            logger.info(
                "   ✓ Cache habilitations bootstrap invalidé"
            )
        except Exception as e:
            logger.debug(f"Cache invalidation (non bloquant) : {e}")
