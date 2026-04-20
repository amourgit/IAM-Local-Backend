from typing import Optional, List
from uuid import UUID
from sqlalchemy import select, and_
from sqlalchemy.orm import selectinload
from sqlalchemy.ext.asyncio import AsyncSession
from app.repositories.base import BaseRepository
from app.models.profil_local import ProfilLocal
from app.models.compte_local import CompteLocal
from app.models.assignation_role import AssignationRole
from app.models.assignation_groupe import AssignationGroupe


class ProfilLocalRepository(BaseRepository[ProfilLocal]):

    def __init__(self, db: AsyncSession):
        super().__init__(ProfilLocal, db)

    # ── Lookups par compte ────────────────────────────────

    async def get_by_compte_id(
        self, compte_id: UUID
    ) -> List[ProfilLocal]:
        """Tous les profils d'un compte local (plusieurs inscriptions)."""
        result = await self.db.execute(
            select(ProfilLocal).where(
                and_(
                    ProfilLocal.compte_id  == compte_id,
                    ProfilLocal.is_deleted == False,
                )
            ).order_by(ProfilLocal.created_at)
        )
        return list(result.scalars().all())

    async def get_actif_by_compte_id(
        self, compte_id: UUID
    ) -> List[ProfilLocal]:
        """Profils actifs d'un compte local."""
        result = await self.db.execute(
            select(ProfilLocal).where(
                and_(
                    ProfilLocal.compte_id  == compte_id,
                    ProfilLocal.statut.in_(["actif", "bootstrap"]),
                    ProfilLocal.is_deleted == False,
                )
            ).order_by(ProfilLocal.created_at)
        )
        return list(result.scalars().all())

    async def get_premier_par_compte(
        self, compte_id: UUID
    ) -> Optional[ProfilLocal]:
        """Premier profil créé pour un compte (profil principal)."""
        result = await self.db.execute(
            select(ProfilLocal).where(
                and_(
                    ProfilLocal.compte_id  == compte_id,
                    ProfilLocal.is_deleted == False,
                )
            ).order_by(ProfilLocal.created_at).limit(1)
        )
        return result.scalar_one_or_none()

    # ── Lookups via CompteLocal (jointure) ────────────────

    async def get_by_user_id_national(
        self, user_id_national: UUID
    ) -> Optional[ProfilLocal]:
        """
        Récupère le profil principal (premier créé) pour un user_id_national.
        Utilisé lors d'une connexion SSO pour trouver le profil à activer.
        """
        result = await self.db.execute(
            select(ProfilLocal)
            .join(CompteLocal, ProfilLocal.compte_id == CompteLocal.id)
            .where(
                and_(
                    CompteLocal.user_id_national == user_id_national,
                    CompteLocal.is_deleted       == False,
                    ProfilLocal.is_deleted       == False,
                )
            )
            .order_by(ProfilLocal.created_at)
            .limit(1)
        )
        return result.scalar_one_or_none()

    async def get_all_by_user_id_national(
        self, user_id_national: UUID
    ) -> List[ProfilLocal]:
        """Tous les profils pour un user_id_national donné."""
        result = await self.db.execute(
            select(ProfilLocal)
            .join(CompteLocal, ProfilLocal.compte_id == CompteLocal.id)
            .where(
                and_(
                    CompteLocal.user_id_national == user_id_national,
                    CompteLocal.is_deleted       == False,
                    ProfilLocal.is_deleted       == False,
                )
            )
            .order_by(ProfilLocal.created_at)
        )
        return list(result.scalars().all())

    # ── Lookups directs ───────────────────────────────────

    async def get_by_username(
        self, username: str
    ) -> Optional[ProfilLocal]:
        result = await self.db.execute(
            select(ProfilLocal).where(
                and_(
                    ProfilLocal.username   == username,
                    ProfilLocal.is_deleted == False,
                )
            )
        )
        return result.scalar_one_or_none()

    async def get_by_email(self, email: str) -> Optional[ProfilLocal]:
        """Lookup par email via jointure avec CompteLocal."""
        result = await self.db.execute(
            select(ProfilLocal)
            .join(CompteLocal, ProfilLocal.compte_id == CompteLocal.id)
            .where(
                and_(
                    CompteLocal.email      == email,
                    CompteLocal.is_deleted == False,
                    ProfilLocal.is_deleted == False,
                )
            )
            .order_by(ProfilLocal.created_at)
            .limit(1)
        )
        return result.scalar_one_or_none()

    async def get_by_identifiant_national(
        self, identifiant_national: str
    ) -> Optional[ProfilLocal]:
        """Lookup par identifiant_national via jointure avec CompteLocal."""
        result = await self.db.execute(
            select(ProfilLocal)
            .join(CompteLocal, ProfilLocal.compte_id == CompteLocal.id)
            .where(
                and_(
                    CompteLocal.identifiant_national == identifiant_national,
                    CompteLocal.is_deleted           == False,
                    ProfilLocal.is_deleted           == False,
                )
            )
            .order_by(ProfilLocal.created_at)
            .limit(1)
        )
        return result.scalar_one_or_none()

    async def get_by_type(self, type_profil: str) -> List[ProfilLocal]:
        result = await self.db.execute(
            select(ProfilLocal).where(
                and_(
                    ProfilLocal.type_profil == type_profil,
                    ProfilLocal.is_deleted  == False,
                )
            ).order_by(ProfilLocal.created_at)
        )
        return list(result.scalars().all())

    async def get_by_statut(self, statut: str) -> List[ProfilLocal]:
        result = await self.db.execute(
            select(ProfilLocal).where(
                and_(
                    ProfilLocal.statut     == statut,
                    ProfilLocal.is_deleted == False,
                )
            )
        )
        return list(result.scalars().all())

    async def get_with_assignations(
        self, id: UUID
    ) -> Optional[ProfilLocal]:
        """Profil avec toutes ses assignations (rôles, groupes, délégations)."""
        result = await self.db.execute(
            select(ProfilLocal)
            .options(
                selectinload(ProfilLocal.compte),
                selectinload(ProfilLocal.assignations_role)
                .selectinload(AssignationRole.role),
                selectinload(ProfilLocal.assignations_groupe)
                .selectinload(AssignationGroupe.groupe),
                selectinload(ProfilLocal.delegations_recues),
            )
            .where(
                and_(
                    ProfilLocal.id         == id,
                    ProfilLocal.is_deleted == False,
                )
            )
        )
        return result.scalar_one_or_none()

    async def get_with_compte(self, id: UUID) -> Optional[ProfilLocal]:
        """Profil avec son CompteLocal chargé (eager)."""
        result = await self.db.execute(
            select(ProfilLocal)
            .options(selectinload(ProfilLocal.compte))
            .where(
                and_(
                    ProfilLocal.id         == id,
                    ProfilLocal.is_deleted == False,
                )
            )
        )
        return result.scalar_one_or_none()

    async def search(self, q: str) -> List[ProfilLocal]:
        """Recherche sur les champs du ProfilLocal ET du CompteLocal parent."""
        result = await self.db.execute(
            select(ProfilLocal)
            .join(CompteLocal, ProfilLocal.compte_id == CompteLocal.id)
            .where(
                and_(
                    ProfilLocal.is_deleted == False,
                    CompteLocal.is_deleted == False,
                    (
                        CompteLocal.nom.ilike(f"%{q}%")
                        | CompteLocal.prenom.ilike(f"%{q}%")
                        | CompteLocal.email.ilike(f"%{q}%")
                        | CompteLocal.identifiant_national.ilike(f"%{q}%")
                        | ProfilLocal.username.ilike(f"%{q}%")
                    )
                )
            ).order_by(CompteLocal.nom, CompteLocal.prenom)
        )
        return list(result.scalars().all())
