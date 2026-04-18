from uuid import UUID
from typing import Optional, Any, List
from datetime import datetime, timezone
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, and_
from app.repositories.profil_local import ProfilLocalRepository
from app.repositories.compte_local import CompteLocalRepository
from app.repositories.assignation_role import AssignationRoleRepository
from app.repositories.assignation_groupe import AssignationGroupeRepository
from app.repositories.permission import PermissionRepository
from app.models.role import Role, role_permissions_table
from app.models.groupe import GroupeRole
from app.models.delegation import Delegation
from app.models.permission import Permission
from app.schemas.habilitation import (
    HabilitationsSchema,
    PermissionEffective,
    VerifierPermissionSchema,
    ResultatVerificationSchema,
)
from app.core.exceptions import NotFoundError
from app.services.audit_service import AuditService
from app.infrastructure.cache.redis import CacheService


class HabilitationService:
    """
    Cœur du système IAM Local.
    Calcule les permissions effectives d'un profil
    en combinant toutes les sources :
    - Rôles directs
    - Rôles via groupes
    - Délégations reçues actives
    """

    def __init__(self, db: AsyncSession):
        self.db           = db
        self.profil_repo  = ProfilLocalRepository(db)
        self.compte_repo  = CompteLocalRepository(db)
        self.assign_role  = AssignationRoleRepository(db)
        self.assign_groupe= AssignationGroupeRepository(db)
        self.perm_repo    = PermissionRepository(db)
        self.audit        = AuditService(db)
        self.cache        = CacheService()

    async def get_habilitations(
        self, profil_id: UUID
    ) -> HabilitationsSchema:
        """
        Retourne toutes les habilitations d'un profil.
        Résultat mis en cache Redis 15 minutes.
        """
        cache_key = f"iam:habilitations:{profil_id}"
        cached    = await self.cache.get(cache_key)
        if cached:
            return HabilitationsSchema(**cached)

        profil = await self.profil_repo.get_by_id(profil_id)
        if not profil:
            raise NotFoundError("Profil", str(profil_id))

        # Récupérer le CompteLocal pour user_id_national
        compte = await self.compte_repo.get_by_id(profil.compte_id)
        user_id_national = compte.user_id_national if compte else None

        permissions_effectives = []
        roles_actifs           = []
        groupes_actifs         = []

        # ── 1. Rôles directs ──────────────────────────────
        assignations_role = await self.assign_role.get_by_profil(
            profil_id, actives_seulement=True
        )

        for assignation in assignations_role:
            role = assignation.role
            if not role or not role.actif:
                continue

            roles_actifs.append(role.code)

            # Récupérer les permissions du rôle
            perms = await self._get_permissions_role(role.id)
            for perm in perms:
                permissions_effectives.append(
                    PermissionEffective(
                        id        = perm.id,        # ✅ Ajouté
                        code      = perm.code,
                        nom       = perm.nom,
                        domaine   = perm.domaine,
                        ressource = perm.ressource,
                        action    = perm.action,
                        perimetre = assignation.perimetre,
                        source    = f"role:{role.code}",
                    )
                )

        # ── 2. Rôles via groupes ──────────────────────────
        assignations_groupe = await self.assign_groupe.get_by_profil(
            profil_id, actives_seulement=True
        )

        for assignation_g in assignations_groupe:
            groupe = assignation_g.groupe
            if not groupe or not groupe.actif:
                continue

            groupes_actifs.append(groupe.code)

            # Récupérer les rôles du groupe
            groupe_roles = await self._get_roles_groupe(groupe.id)
            for groupe_role in groupe_roles:
                role = groupe_role.role
                if not role or not role.actif:
                    continue

                if role.code not in roles_actifs:
                    roles_actifs.append(role.code)

                # Périmètre = périmètre du groupe_role
                # ou périmètre du groupe si non défini
                perimetre = (
                    groupe_role.perimetre
                    or groupe.perimetre
                )

                perms = await self._get_permissions_role(role.id)
                for perm in perms:
                    permissions_effectives.append(
                        PermissionEffective(
                            id        = perm.id,        # ✅ Ajouté
                            code      = perm.code,
                            nom       = perm.nom,
                            domaine   = perm.domaine,
                            ressource = perm.ressource,
                            action    = perm.action,
                            perimetre = perimetre,
                            source    = f"groupe:{groupe.code}",
                        )
                    )

        # ── 3. Délégations reçues actives ─────────────────
        delegations = await self._get_delegations_actives(profil_id)

        for delegation in delegations:
            if delegation.role_id:
                role_result = await self.db.execute(
                    select(Role).where(Role.id == delegation.role_id)
                )
                role = role_result.scalar_one_or_none()
                if role and role.actif:
                    perms = await self._get_permissions_role(role.id)
                    for perm in perms:
                        permissions_effectives.append(
                            PermissionEffective(
                                id        = perm.id,        # ✅ Ajouté
                                code      = perm.code,
                                nom       = perm.nom,
                                domaine   = perm.domaine,
                                ressource = perm.ressource,
                                action    = perm.action,
                                perimetre = delegation.perimetre,
                                source    = f"delegation:{delegation.id}",
                            )
                        )
            elif delegation.permissions_specifiques:
                for code in delegation.permissions_specifiques:
                    perm = await self.perm_repo.get_by_code(code)
                    if perm and perm.actif:
                        permissions_effectives.append(
                            PermissionEffective(
                                id        = perm.id,        # ✅ Ajouté
                                code      = perm.code,
                                nom       = perm.nom,
                                domaine   = perm.domaine,
                                ressource = perm.ressource,
                                action    = perm.action,
                                perimetre = delegation.perimetre,
                                source    = f"delegation:{delegation.id}",
                            )
                        )

        habilitations = HabilitationsSchema(
            profil_id        = profil_id,
            user_id_national = user_id_national,
            type_profil      = profil.type_profil,
            statut           = profil.statut,
            permissions      = permissions_effectives,
            roles_actifs     = list(set(roles_actifs)),
            groupes_actifs   = list(set(groupes_actifs)),
        )

        # Mettre en cache 15 minutes
        await self.cache.set(
            cache_key,
            habilitations.model_dump(),
            ttl = 900,
        )

        return habilitations

    async def verifier_permission(
        self,
        profil_id  : UUID,
        data       : VerifierPermissionSchema,
        request_id : Optional[str] = None,
    ) -> ResultatVerificationSchema:
        """
        Vérifie si un profil a une permission sur un périmètre.
        Endpoint central appelé par tous les microservices.
        """

        profil = await self.profil_repo.get_by_id(profil_id)
        if not profil:
            resultat = ResultatVerificationSchema(
                autorise   = False,
                permission = data.permission,
                perimetre  = data.perimetre,
                raison     = "Profil introuvable",
            )
            return resultat

        if profil.statut != "actif":
            resultat = ResultatVerificationSchema(
                autorise         = False,
                permission       = data.permission,
                perimetre        = data.perimetre,
                raison           = f"Profil {profil.statut}",
                profil_id        = profil_id,
                user_id_national = user_id_national,
            )
            await self.audit.log_verification_permission(
                profil_id        = profil_id,
                user_id_national = user_id_national,
                permission       = data.permission,
                perimetre        = data.perimetre,
                autorise         = False,
                raison           = f"Profil {profil.statut}",
                request_id       = request_id,
            )
            return resultat

        # Récupérer toutes les habilitations (depuis cache si dispo)
        habilitations = await self.get_habilitations(profil_id)

        # Chercher la permission demandée
        for perm_effective in habilitations.permissions:
            if perm_effective.code != data.permission:
                continue

            # Permission trouvée — vérifier le périmètre
            if data.perimetre and perm_effective.perimetre:
                if not self._perimetre_compatible(
                    data.perimetre, perm_effective.perimetre
                ):
                    continue

            # Autorisé
            resultat = ResultatVerificationSchema(
                autorise         = True,
                permission       = data.permission,
                perimetre        = data.perimetre,
                source           = perm_effective.source,
                profil_id        = profil_id,
                user_id_national = user_id_national,
            )

            await self.audit.log_verification_permission(
                profil_id        = profil_id,
                user_id_national = user_id_national,
                permission       = data.permission,
                perimetre        = data.perimetre,
                autorise         = True,
                request_id       = request_id,
            )

            return resultat

        # Permission non trouvée — refusé
        resultat = ResultatVerificationSchema(
            autorise         = False,
            permission       = data.permission,
            perimetre        = data.perimetre,
            raison           = "Permission non accordée",
            profil_id        = profil_id,
            user_id_national = user_id_national,
        )

        await self.audit.log_verification_permission(
            profil_id        = profil_id,
            user_id_national = user_id_national,
            permission       = data.permission,
            perimetre        = data.perimetre,
            autorise         = False,
            raison           = "Permission non accordée",
            request_id       = request_id,
        )

        return resultat

    async def invalider_cache(self, profil_id: UUID) -> None:
        """
        À appeler après toute modification d'habilitation.
        Invalide le cache pour forcer le recalcul.
        """
        await self.cache.delete(f"iam:habilitations:{profil_id}")

    def _perimetre_compatible(
        self,
        demande   : dict,
        accordee  : dict,
    ) -> bool:
        """
        Vérifie si le périmètre demandé est couvert
        par le périmètre accordé.
        Le périmètre accordé peut être plus large
        (ex: campus entier > composante spécifique).
        """
        for cle, valeur in demande.items():
            if cle in accordee:
                if str(accordee[cle]) != str(valeur):
                    return False
        return True

    async def _get_permissions_role(
        self, role_id: UUID
    ) -> List[Permission]:
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

    async def _get_roles_groupe(
        self, groupe_id: UUID
    ) -> List[GroupeRole]:
        result = await self.db.execute(
            select(GroupeRole)
            .where(
                and_(
                    GroupeRole.groupe_id  == groupe_id,
                    GroupeRole.is_deleted == False,
                )
            )
        )
        return list(result.scalars().all())

    async def _get_delegations_actives(
        self, profil_id: UUID
    ) -> List[Delegation]:
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
