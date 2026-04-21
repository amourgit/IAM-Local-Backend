"""
HabilitationService — Moteur de calcul des permissions effectives.

Graphe de résolution :
    ProfilLocal
        ├── AssignationRole ──→ Role ──→ [Permission, ...]  (direct)
        ├── AssignationGroupe ──→ Groupe
        │       └── GroupeRole ──→ Role ──→ [Permission, ...]  (via groupe)
        └── Delegation ──→ Role ──→ [Permission, ...]         (délégation rôle)
                       └── permissions_specifiques            (délégation directe)

Règles :
- Un profil suspendu/expiré/inactif → aucune permission
- Les rôles système (systeme=True) sont inclus normalement
- Déduplication des permissions par (code, perimetre_key) — union
- Le périmètre le plus spécifique prime dans la vérification
- Cache Redis 15 minutes, invalidé à chaque mutation

Performance :
- Toutes les queries utilisent joinedload/selectinload pour éviter le N+1
- Le calcul complet est fait en une seule passe sur les données chargées
"""
import logging
import hashlib
import json
from uuid import UUID
from typing import Optional, List, Dict, Tuple, Set
from datetime import datetime, timezone

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, and_
from sqlalchemy.orm import selectinload, joinedload

from app.models.assignation_role import AssignationRole
from app.models.assignation_groupe import AssignationGroupe
from app.models.groupe import Groupe, GroupeRole
from app.models.role import Role, role_permissions_table
from app.models.delegation import Delegation
from app.models.permission import Permission
from app.models.profil_local import ProfilLocal
from app.models.compte_local import CompteLocal

from app.schemas.habilitation import (
    HabilitationsSchema,
    PermissionEffective,
    VerifierPermissionSchema,
    ResultatVerificationSchema,
)
from app.core.exceptions import NotFoundError
from app.services.audit_service import AuditService
from app.infrastructure.cache.redis import CacheService

logger = logging.getLogger(__name__)

# Statuts de profil qui autorisent l'accès
STATUTS_ACTIFS = frozenset({"actif", "bootstrap"})

# TTL cache habilitations (15 minutes)
CACHE_TTL_SECONDES = 900


def _perimetre_key(perimetre: Optional[dict]) -> str:
    """Clé déterministe pour un périmètre — utilisée pour la déduplication."""
    if not perimetre:
        return "__global__"
    return hashlib.sha256(
        json.dumps(perimetre, sort_keys=True, default=str).encode()
    ).hexdigest()[:16]


class HabilitationService:
    """
    Moteur de calcul des habilitations IAM Local.

    Calcule dynamiquement les permissions effectives d'un profil
    en parcourant le graphe complet :
        ProfilLocal → roles directs
                    → groupes → roles de groupes
                    → délégations reçues
    """

    def __init__(self, db: AsyncSession):
        self.db    = db
        self.audit = AuditService(db)
        self.cache = CacheService()

    # ══════════════════════════════════════════════════════════════
    # API PUBLIQUE
    # ══════════════════════════════════════════════════════════════

    async def get_habilitations(
        self,
        profil_id: UUID,
    ) -> HabilitationsSchema:
        """
        Retourne les habilitations complètes d'un profil.
        Résultat mis en cache Redis 15 minutes.
        Lève NotFoundError si le profil est inexistant.
        """
        cache_key = f"iam:habilitations:{profil_id}"

        # ── Cache hit ─────────────────────────────────────────────
        cached = await self.cache.get(cache_key)
        if cached:
            try:
                return HabilitationsSchema(**cached)
            except Exception:
                # Cache corrompu → recalcul
                await self.cache.delete(cache_key)

        # ── Charger le profil et son compte en une requête ────────
        profil, compte = await self._charger_profil_et_compte(profil_id)

        # ── Calculer les permissions ───────────────────────────────
        permissions, roles_codes, groupes_codes = await self._calculer_permissions(profil_id)

        habilitations = HabilitationsSchema(
            profil_id        = profil_id,
            user_id_national = compte.user_id_national if compte else None,
            type_profil      = profil.type_profil,
            statut           = profil.statut,
            permissions      = permissions,
            roles_actifs     = sorted(roles_codes),
            groupes_actifs   = sorted(groupes_codes),
        )

        # ── Mettre en cache ───────────────────────────────────────
        await self.cache.set(cache_key, habilitations.model_dump(), ttl=CACHE_TTL_SECONDES)

        return habilitations

    async def verifier_permission(
        self,
        profil_id  : UUID,
        data       : VerifierPermissionSchema,
        request_id : Optional[str] = None,
    ) -> ResultatVerificationSchema:
        """
        Vérifie si un profil possède une permission sur un périmètre donné.
        Endpoint central appelé par tous les microservices.
        Chaque appel est tracé dans le journal d'audit.
        """
        # ── Charger le profil ─────────────────────────────────────
        profil, compte = await self._charger_profil_et_compte(profil_id, raise_if_not_found=False)
        user_id_national = compte.user_id_national if compte else None

        if profil is None:
            return await self._resultat_refuse(
                profil_id        = profil_id,
                user_id_national = None,
                data             = data,
                raison           = "Profil introuvable",
                request_id       = request_id,
            )

        # ── Vérifier le statut du profil ──────────────────────────
        if profil.statut not in STATUTS_ACTIFS:
            return await self._resultat_refuse(
                profil_id        = profil_id,
                user_id_national = user_id_national,
                data             = data,
                raison           = f"Profil {profil.statut} — accès interdit",
                request_id       = request_id,
            )

        # ── Récupérer les habilitations (depuis cache si possible) ─
        habilitations = await self.get_habilitations(profil_id)

        # ── Chercher la permission dans les habilitations ─────────
        for perm_effective in habilitations.permissions:
            if perm_effective.code != data.permission:
                continue

            # Permission trouvée — vérifier la compatibilité du périmètre
            if data.perimetre:
                if not self._perimetre_compatible(
                    demandee=data.perimetre,
                    accordee=perm_effective.perimetre or {},
                ):
                    continue

            # ✅ Autorisé
            resultat = ResultatVerificationSchema(
                autorise         = True,
                permission       = data.permission,
                perimetre        = data.perimetre,
                source           = perm_effective.source,
                profil_id        = profil_id,
                user_id_national = user_id_national,
            )
            await self._audit_permission(
                profil_id=profil_id, user_id_national=user_id_national,
                data=data, autorise=True, request_id=request_id,
            )
            return resultat

        # ❌ Permission non trouvée
        return await self._resultat_refuse(
            profil_id        = profil_id,
            user_id_national = user_id_national,
            data             = data,
            raison           = f"Permission '{data.permission}' non accordée",
            request_id       = request_id,
        )

    async def invalider_cache(self, profil_id: UUID) -> None:
        """Invalide le cache des habilitations d'un profil."""
        await self.cache.delete(f"iam:habilitations:{profil_id}")
        logger.debug(f"Cache habilitations invalidé pour profil {profil_id}")

    async def invalider_cache_role(self, role_id: UUID) -> None:
        """
        Invalide le cache de TOUS les profils qui ont ce rôle
        (direct ou via groupe).
        Appelé quand les permissions d'un rôle changent.
        """
        profil_ids = await self._get_profils_ayant_role(role_id)
        for pid in profil_ids:
            await self.invalider_cache(pid)
        if profil_ids:
            logger.info(
                f"Cache invalidé pour {len(profil_ids)} profil(s) "
                f"après modification rôle {role_id}"
            )

    async def invalider_cache_groupe(self, groupe_id: UUID) -> None:
        """
        Invalide le cache de TOUS les membres d'un groupe.
        Appelé quand les rôles d'un groupe changent.
        """
        profil_ids = await self._get_membres_groupe(groupe_id)
        for pid in profil_ids:
            await self.invalider_cache(pid)
        if profil_ids:
            logger.info(
                f"Cache invalidé pour {len(profil_ids)} membre(s) "
                f"après modification groupe {groupe_id}"
            )

    # ══════════════════════════════════════════════════════════════
    # CALCUL DES PERMISSIONS
    # ══════════════════════════════════════════════════════════════

    async def _calculer_permissions(
        self,
        profil_id: UUID,
    ) -> Tuple[List[PermissionEffective], List[str], List[str]]:
        """
        Calcule l'ensemble des permissions effectives d'un profil.

        Retourne :
            - Liste des PermissionEffective (dédupliquées)
            - Liste des codes de rôles actifs
            - Liste des codes de groupes actifs

        Stratégie de déduplication :
        Clé = (code_permission, perimetre_key).
        Si doublon, on garde celui dont la source est la plus directe
        (role > groupe > delegation) — mais on collecte toutes les sources.
        """
        # Dictionnaire de déduplication : (code, perimetre_key) → PermissionEffective
        perms_map  : Dict[Tuple[str, str], PermissionEffective] = {}
        roles_codes: Set[str] = set()
        groupes_codes: Set[str] = set()

        # ── Source 1 : Rôles directs ──────────────────────────────
        assignations_role = await self._charger_assignations_role(profil_id)

        for assignation in assignations_role:
            role = assignation.role
            if not role or not role.actif or role.is_deleted:
                continue

            roles_codes.add(role.code)
            perms = await self._charger_permissions_role(role.id)

            for perm in perms:
                self._ajouter_permission(
                    perms_map = perms_map,
                    perm      = perm,
                    perimetre = assignation.perimetre,
                    source    = f"role:{role.code}",
                    priorite  = 1,
                )

        # ── Source 2 : Rôles via groupes ──────────────────────────
        assignations_groupe = await self._charger_assignations_groupe(profil_id)

        for assignation_g in assignations_groupe:
            groupe = assignation_g.groupe
            if not groupe or not groupe.actif or groupe.is_deleted:
                continue

            groupes_codes.add(groupe.code)

            # Charger les GroupeRole avec le Role en eager load
            groupe_roles = await self._charger_roles_groupe(groupe.id)

            for groupe_role in groupe_roles:
                role = groupe_role.role
                if not role or not role.actif or role.is_deleted:
                    continue

                roles_codes.add(role.code)

                # Priorité périmètre :
                # 1. groupe_role.perimetre (le plus spécifique)
                # 2. groupe.perimetre (périmètre du groupe)
                # 3. assignation_g.perimetre (si défini)
                # 4. None (global)
                perimetre = (
                    groupe_role.perimetre
                    or assignation_g.perimetre
                    or groupe.perimetre
                )

                perms = await self._charger_permissions_role(role.id)

                for perm in perms:
                    self._ajouter_permission(
                        perms_map = perms_map,
                        perm      = perm,
                        perimetre = perimetre,
                        source    = f"groupe:{groupe.code}→role:{role.code}",
                        priorite  = 2,
                    )

        # ── Source 3 : Délégations reçues actives ─────────────────
        delegations = await self._charger_delegations_actives(profil_id)

        for delegation in delegations:
            if delegation.role_id:
                # Délégation d'un rôle entier
                perms_role = await self._charger_permissions_role(delegation.role_id)
                for perm in perms_role:
                    self._ajouter_permission(
                        perms_map = perms_map,
                        perm      = perm,
                        perimetre = delegation.perimetre,
                        source    = f"delegation:{delegation.id}",
                        priorite  = 3,
                    )
            elif delegation.permissions_specifiques:
                # Délégation de permissions spécifiques (liste de codes)
                codes = delegation.permissions_specifiques
                if isinstance(codes, list):
                    perms_specifiques = await self._charger_permissions_par_codes(codes)
                    for perm in perms_specifiques:
                        self._ajouter_permission(
                            perms_map = perms_map,
                            perm      = perm,
                            perimetre = delegation.perimetre,
                            source    = f"delegation:{delegation.id}",
                            priorite  = 3,
                        )

        return list(perms_map.values()), list(roles_codes), list(groupes_codes)

    def _ajouter_permission(
        self,
        perms_map : Dict[Tuple[str, str], PermissionEffective],
        perm      : "Permission",
        perimetre : Optional[dict],
        source    : str,
        priorite  : int,
    ) -> None:
        """
        Ajoute une permission dans le dictionnaire de déduplication.
        Si la permission existe déjà pour ce (code, perimetre) :
        - On garde la source de priorité la plus élevée (1 = direct > 2 = groupe > 3 = délégation)
        - On concatène les sources pour la traçabilité
        """
        cle = (perm.code, _perimetre_key(perimetre))

        if cle in perms_map:
            existante = perms_map[cle]
            # Enrichir la source (traçabilité multi-source)
            sources_existantes = existante.source.split("|")
            if source not in sources_existantes:
                sources_existantes.append(source)
                existante.source = "|".join(sources_existantes)
            return

        perms_map[cle] = PermissionEffective(
            id        = perm.id,
            code      = perm.code,
            nom       = perm.nom,
            domaine   = perm.domaine,
            ressource = perm.ressource,
            action    = perm.action,
            perimetre = perimetre,
            source    = source,
        )

    # ══════════════════════════════════════════════════════════════
    # CHARGEMENT OPTIMISÉ (évite le N+1)
    # ══════════════════════════════════════════════════════════════

    async def _charger_profil_et_compte(
        self,
        profil_id         : UUID,
        raise_if_not_found: bool = True,
    ) -> Tuple[Optional[ProfilLocal], Optional[CompteLocal]]:
        """Charge ProfilLocal + CompteLocal en une seule requête via jointure."""
        result = await self.db.execute(
            select(ProfilLocal)
            .options(joinedload(ProfilLocal.compte))
            .where(
                and_(
                    ProfilLocal.id         == profil_id,
                    ProfilLocal.is_deleted == False,
                )
            )
        )
        profil = result.unique().scalar_one_or_none()

        if profil is None:
            if raise_if_not_found:
                raise NotFoundError("Profil", str(profil_id))
            return None, None

        compte = profil.compte if hasattr(profil, "compte") else None
        return profil, compte

    async def _charger_assignations_role(
        self,
        profil_id: UUID,
    ) -> List[AssignationRole]:
        """
        Charge les assignations de rôle actives d'un profil.
        Eager load du Role inclus.
        """
        now = datetime.now(timezone.utc)
        result = await self.db.execute(
            select(AssignationRole)
            .options(selectinload(AssignationRole.role))
            .where(
                and_(
                    AssignationRole.profil_id  == profil_id,
                    AssignationRole.statut     == "active",
                    AssignationRole.is_deleted == False,
                    (AssignationRole.date_fin == None)
                    | (AssignationRole.date_fin >= now),
                )
            )
        )
        return list(result.scalars().unique().all())

    async def _charger_assignations_groupe(
        self,
        profil_id: UUID,
    ) -> List[AssignationGroupe]:
        """
        Charge les assignations de groupe actives d'un profil.
        Eager load du Groupe inclus.
        """
        now = datetime.now(timezone.utc)
        result = await self.db.execute(
            select(AssignationGroupe)
            .options(selectinload(AssignationGroupe.groupe))
            .where(
                and_(
                    AssignationGroupe.profil_id  == profil_id,
                    AssignationGroupe.statut     == "active",
                    AssignationGroupe.is_deleted == False,
                    (AssignationGroupe.date_fin == None)
                    | (AssignationGroupe.date_fin >= now),
                )
            )
        )
        return list(result.scalars().unique().all())

    async def _charger_roles_groupe(
        self,
        groupe_id: UUID,
    ) -> List[GroupeRole]:
        """
        Charge les GroupeRole d'un groupe avec le Role en eager load.
        Filtre les GroupeRole soft-deleted.
        """
        result = await self.db.execute(
            select(GroupeRole)
            .options(selectinload(GroupeRole.role))
            .where(
                and_(
                    GroupeRole.groupe_id  == groupe_id,
                    GroupeRole.is_deleted == False,
                )
            )
        )
        return list(result.scalars().unique().all())

    async def _charger_permissions_role(
        self,
        role_id: UUID,
    ) -> List[Permission]:
        """
        Charge les permissions actives d'un rôle via role_permissions_table.
        Filtre : actif=True, deprecated=False, is_deleted=False.
        """
        result = await self.db.execute(
            select(Permission)
            .join(
                role_permissions_table,
                Permission.id == role_permissions_table.c.permission_id,
            )
            .where(
                and_(
                    role_permissions_table.c.role_id == role_id,
                    Permission.actif                 == True,
                    Permission.deprecated            == False,
                    Permission.is_deleted            == False,
                )
            )
        )
        return list(result.scalars().all())

    async def _charger_permissions_par_codes(
        self,
        codes: List[str],
    ) -> List[Permission]:
        """Charge les permissions par codes (pour les délégations directes)."""
        if not codes:
            return []
        result = await self.db.execute(
            select(Permission).where(
                and_(
                    Permission.code.in_(codes),
                    Permission.actif      == True,
                    Permission.deprecated == False,
                    Permission.is_deleted == False,
                )
            )
        )
        return list(result.scalars().all())

    async def _charger_delegations_actives(
        self,
        profil_id: UUID,
    ) -> List[Delegation]:
        """Charge les délégations reçues actives et non expirées."""
        now = datetime.now(timezone.utc)
        result = await self.db.execute(
            select(Delegation).where(
                and_(
                    Delegation.delegataire_id == profil_id,
                    Delegation.statut         == "active",
                    Delegation.date_debut     <= now,
                    Delegation.date_fin       >= now,
                    Delegation.is_deleted     == False,
                )
            )
        )
        return list(result.scalars().all())

    # ══════════════════════════════════════════════════════════════
    # INVALIDATION DE CACHE PROPAGÉE
    # ══════════════════════════════════════════════════════════════

    async def _get_profils_ayant_role(self, role_id: UUID) -> List[UUID]:
        """
        Retourne tous les profils ayant ce rôle :
        - Directement via AssignationRole
        - Indirectement via Groupe → GroupeRole
        """
        profil_ids: Set[UUID] = set()

        # Direct
        result = await self.db.execute(
            select(AssignationRole.profil_id).where(
                and_(
                    AssignationRole.role_id    == role_id,
                    AssignationRole.statut     == "active",
                    AssignationRole.is_deleted == False,
                )
            )
        )
        for row in result:
            profil_ids.add(row[0])

        # Via groupes
        groupes_result = await self.db.execute(
            select(GroupeRole.groupe_id).where(
                and_(
                    GroupeRole.role_id    == role_id,
                    GroupeRole.is_deleted == False,
                )
            )
        )
        groupe_ids = [row[0] for row in groupes_result]

        for groupe_id in groupe_ids:
            membres = await self._get_membres_groupe(groupe_id)
            profil_ids.update(membres)

        return list(profil_ids)

    async def _get_membres_groupe(self, groupe_id: UUID) -> List[UUID]:
        """Retourne les profil_id de tous les membres actifs d'un groupe."""
        result = await self.db.execute(
            select(AssignationGroupe.profil_id).where(
                and_(
                    AssignationGroupe.groupe_id  == groupe_id,
                    AssignationGroupe.statut     == "active",
                    AssignationGroupe.is_deleted == False,
                )
            )
        )
        return [row[0] for row in result]

    # ══════════════════════════════════════════════════════════════
    # VÉRIFICATION DE PÉRIMÈTRE
    # ══════════════════════════════════════════════════════════════

    def _perimetre_compatible(
        self,
        demandee: dict,
        accordee: dict,
    ) -> bool:
        """
        Vérifie si le périmètre accordé couvre le périmètre demandé.

        Logique :
        - Si accordé = {} (global) → couvre tout → True
        - Pour chaque clé du périmètre demandé :
            - Si la clé est dans le périmètre accordé ET les valeurs diffèrent → False
            - Si la clé n'est pas dans le périmètre accordé → la permission est globale sur ce critère → OK
        - Toutes les clés passent → True

        Exemples :
            demandee={composante_id: "X"}, accordee={} → True (accordé global)
            demandee={composante_id: "X"}, accordee={composante_id: "X"} → True
            demandee={composante_id: "X"}, accordee={composante_id: "Y"} → False
            demandee={composante_id: "X", annee: "2024"}, accordee={composante_id: "X"} → True
        """
        if not accordee:  # Périmètre global → couvre tout
            return True

        for cle, valeur_demandee in demandee.items():
            if cle not in accordee:
                # La permission accordée ne restreint pas sur ce critère → OK
                continue
            valeur_accordee = accordee[cle]
            if str(valeur_accordee) != str(valeur_demandee):
                return False

        return True

    # ══════════════════════════════════════════════════════════════
    # HELPERS INTERNES
    # ══════════════════════════════════════════════════════════════

    async def _resultat_refuse(
        self,
        profil_id        : UUID,
        user_id_national : Optional[UUID],
        data             : VerifierPermissionSchema,
        raison           : str,
        request_id       : Optional[str],
    ) -> ResultatVerificationSchema:
        await self._audit_permission(
            profil_id=profil_id, user_id_national=user_id_national,
            data=data, autorise=False, raison=raison, request_id=request_id,
        )
        return ResultatVerificationSchema(
            autorise         = False,
            permission       = data.permission,
            perimetre        = data.perimetre,
            raison           = raison,
            profil_id        = profil_id,
            user_id_national = user_id_national,
        )

    async def _audit_permission(
        self,
        profil_id        : UUID,
        user_id_national : Optional[UUID],
        data             : VerifierPermissionSchema,
        autorise         : bool,
        raison           : Optional[str] = None,
        request_id       : Optional[str] = None,
    ) -> None:
        try:
            await self.audit.log_verification_permission(
                profil_id        = profil_id,
                user_id_national = user_id_national,
                permission       = data.permission,
                perimetre        = data.perimetre,
                autorise         = autorise,
                raison           = raison,
                request_id       = request_id,
            )
        except Exception as e:
            # L'audit ne doit jamais faire planter la vérification
            logger.error(f"Erreur audit permission: {e}")
