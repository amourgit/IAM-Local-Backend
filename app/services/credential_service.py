"""
Service de gestion des credentials locaux pour les CompteLocal.

Les credentials (mot de passe) sont portés par CompteLocal, pas par ProfilLocal.
Un CompteLocal peut avoir des credentials pour l'authentification locale
(hors SSO IAM Central). L'authentification retourne un CompteLocal + son ProfilLocal.
"""
import bcrypt
import secrets
import string
from datetime import datetime, timezone, timedelta
from typing import Optional, Dict, Any, Tuple
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, or_, and_

from app.models.compte_local import CompteLocal
from app.models.profil_local import ProfilLocal
from app.core.exceptions import ValidationError, NotFoundError, AuthenticationError
from app.config import settings
import logging

logger = logging.getLogger(__name__)


class CredentialService:
    """
    Service de gestion des credentials pour l'authentification locale.
    Opère sur CompteLocal (porteur des credentials).
    Retourne le CompteLocal + ProfilLocal pour l'AuthService.
    """

    MIN_PASSWORD_LENGTH      = 8
    MAX_PASSWORD_LENGTH      = 128
    MAX_FAILED_ATTEMPTS      = 5
    LOCKOUT_DURATION_MINUTES = 15
    PASSWORD_CHARS           = string.ascii_letters + string.digits + "!@#$%^&*"

    def __init__(self, db: AsyncSession):
        self.db = db

    # ── Authentification ─────────────────────────────────

    async def authenticate_credentials(
        self,
        identifier : str,
        password   : str,
    ) -> Tuple[CompteLocal, ProfilLocal]:
        """
        Authentifie un utilisateur par credentials locaux.
        Retourne (CompteLocal, ProfilLocal) pour construire le user_data.
        """
        compte = await self._get_compte_by_identifier(identifier)
        if not compte:
            raise AuthenticationError("Identifiants invalides")

        if not compte.password_hash:
            raise AuthenticationError(
                "Ce compte n'utilise pas d'authentification locale"
            )

        if self._is_account_locked(compte):
            raise AuthenticationError("Compte temporairement verrouillé")

        if not self._verify_password(password, compte.password_hash):
            await self._handle_failed_attempt(compte)
            raise AuthenticationError("Identifiants invalides")

        await self._handle_successful_login(compte)

        # Récupérer le profil actif associé
        profil = await self._get_profil_actif_du_compte(compte.id)
        if not profil:
            raise AuthenticationError(
                "Aucun profil actif associé à ce compte"
            )

        logger.info(f"Authentification locale réussie pour {identifier}")
        return compte, profil

    # ── Gestion des credentials ───────────────────────────

    async def create_credentials(
        self,
        compte_id      : UUID,
        password       : str,
        require_change : bool = False,
    ) -> bool:
        self._validate_password_strength(password)
        compte = await self._get_compte_by_id(compte_id)
        if not compte:
            raise NotFoundError(f"CompteLocal {compte_id} non trouvé")
        if compte.password_hash:
            raise ValidationError("Ce compte possède déjà des credentials")

        password_hash, password_salt = self.hash_password(password)
        compte.password_hash             = password_hash
        compte.password_salt             = password_salt
        compte.password_algorithm        = "bcrypt"
        compte.password_changed_at       = datetime.now(timezone.utc)
        compte.require_password_change   = require_change
        compte.failed_login_attempts     = 0
        compte.locked_until              = None
        self.db.add(compte)
        await self.db.commit()
        logger.info(f"Credentials créés pour le compte {compte_id}")
        return True

    async def change_password(
        self,
        compte_id    : UUID,
        old_password : str,
        new_password : str,
        force_change : bool = False,
    ) -> bool:
        self._validate_password_strength(new_password)
        compte = await self._get_compte_by_id(compte_id)
        if not compte:
            raise NotFoundError(f"CompteLocal {compte_id} non trouvé")

        if not force_change:
            if not compte.password_hash:
                raise AuthenticationError("Aucun mot de passe défini")
            if not self._verify_password(old_password, compte.password_hash):
                await self._handle_failed_attempt(compte)
                raise AuthenticationError("Ancien mot de passe incorrect")

        password_hash, password_salt = self.hash_password(new_password)
        compte.password_hash           = password_hash
        compte.password_salt           = password_salt
        compte.password_changed_at     = datetime.now(timezone.utc)
        compte.require_password_change = False
        compte.failed_login_attempts   = 0
        compte.locked_until            = None
        self.db.add(compte)
        await self.db.commit()
        logger.info(f"Mot de passe changé pour le compte {compte_id}")
        return True

    async def reset_password(
        self,
        compte_id     : UUID,
        temp_password : Optional[str] = None,
    ) -> str:
        compte = await self._get_compte_by_id(compte_id)
        if not compte:
            raise NotFoundError(f"CompteLocal {compte_id} non trouvé")
        if not temp_password:
            temp_password = self._generate_temp_password()

        password_hash, password_salt = self.hash_password(temp_password)
        compte.password_hash           = password_hash
        compte.password_salt           = password_salt
        compte.password_changed_at     = datetime.now(timezone.utc)
        compte.require_password_change = True
        compte.failed_login_attempts   = 0
        compte.locked_until            = None
        self.db.add(compte)
        await self.db.commit()
        logger.info(f"Mot de passe réinitialisé pour le compte {compte_id}")
        return temp_password

    async def unlock_account(self, compte_id: UUID) -> bool:
        compte = await self._get_compte_by_id(compte_id)
        if not compte:
            raise NotFoundError(f"CompteLocal {compte_id} non trouvé")
        compte.failed_login_attempts = 0
        compte.locked_until          = None
        self.db.add(compte)
        await self.db.commit()
        logger.info(f"Compte déverrouillé : {compte_id}")
        return True

    async def remove_credentials(self, compte_id: UUID) -> bool:
        compte = await self._get_compte_by_id(compte_id)
        if not compte:
            raise NotFoundError(f"CompteLocal {compte_id} non trouvé")
        compte.password_hash             = None
        compte.password_salt             = None
        compte.password_algorithm        = None
        compte.password_changed_at       = None
        compte.failed_login_attempts     = 0
        compte.locked_until              = None
        compte.require_password_change   = False
        self.db.add(compte)
        await self.db.commit()
        logger.info(f"Credentials supprimés pour le compte {compte_id}")
        return True

    async def get_credential_info(self, compte_id: UUID) -> Optional[Dict[str, Any]]:
        compte = await self._get_compte_by_id(compte_id)
        if not compte:
            return None
        return {
            "has_credentials" : compte.password_hash is not None,
            "algorithm"       : compte.password_algorithm,
            "changed_at"      : compte.password_changed_at,
            "failed_attempts" : compte.failed_login_attempts,
            "locked_until"    : compte.locked_until,
            "require_change"  : compte.require_password_change,
            "is_locked"       : self._is_account_locked(compte),
        }

    async def reset_failed_attempts(self, compte_id: UUID) -> bool:
        compte = await self._get_compte_by_id(compte_id)
        if not compte:
            return False
        compte.failed_login_attempts = 0
        compte.locked_until          = None
        self.db.add(compte)
        await self.db.commit()
        return True

    # ── Utilitaires synchrones ────────────────────────────

    def hash_password(self, password: str) -> Tuple[str, str]:
        salt   = bcrypt.gensalt(rounds=12)
        hashed = bcrypt.hashpw(password.encode("utf-8"), salt)
        return hashed.decode("utf-8"), salt.decode("utf-8")

    def _validate_password_strength(self, password: str) -> None:
        if not password:
            raise ValidationError("Le mot de passe ne peut pas être vide")
        if len(password) < self.MIN_PASSWORD_LENGTH:
            raise ValidationError(
                f"Le mot de passe doit contenir au moins "
                f"{self.MIN_PASSWORD_LENGTH} caractères"
            )
        if len(password) > self.MAX_PASSWORD_LENGTH:
            raise ValidationError(
                f"Le mot de passe ne peut pas dépasser "
                f"{self.MAX_PASSWORD_LENGTH} caractères"
            )

    def _verify_password(self, password: str, hashed: str) -> bool:
        try:
            return bcrypt.checkpw(
                password.encode("utf-8"), hashed.encode("utf-8")
            )
        except Exception:
            return False

    def _generate_temp_password(self, length: int = 12) -> str:
        return "".join(secrets.choice(self.PASSWORD_CHARS) for _ in range(length))

    def _is_account_locked(self, compte: CompteLocal) -> bool:
        if not compte.locked_until:
            return False
        return datetime.now(timezone.utc) < compte.locked_until

    async def _handle_failed_attempt(self, compte: CompteLocal) -> None:
        compte.failed_login_attempts += 1
        if compte.failed_login_attempts >= self.MAX_FAILED_ATTEMPTS:
            compte.locked_until = datetime.now(timezone.utc) + timedelta(
                minutes=self.LOCKOUT_DURATION_MINUTES
            )
            logger.warning(
                f"Compte verrouillé pour {compte.username} "
                f"après {compte.failed_login_attempts} tentatives échouées"
            )
        self.db.add(compte)
        await self.db.commit()

    async def _handle_successful_login(self, compte: CompteLocal) -> None:
        compte.failed_login_attempts = 0
        compte.locked_until          = None
        compte.derniere_connexion    = datetime.now(timezone.utc)
        if not compte.premiere_connexion:
            compte.premiere_connexion = compte.derniere_connexion
        try:
            compte.nb_connexions = str(int(compte.nb_connexions or "0") + 1)
        except ValueError:
            compte.nb_connexions = "1"
        self.db.add(compte)
        await self.db.commit()

    # ── Requêtes DB ───────────────────────────────────────

    async def _get_compte_by_id(self, compte_id: UUID) -> Optional[CompteLocal]:
        result = await self.db.execute(
            select(CompteLocal).where(CompteLocal.id == compte_id)
        )
        return result.scalar_one_or_none()

    async def _get_compte_by_identifier(self, identifier: str) -> Optional[CompteLocal]:
        result = await self.db.execute(
            select(CompteLocal).where(
                and_(
                    CompteLocal.is_deleted == False,
                    or_(
                        CompteLocal.email                == identifier,
                        CompteLocal.username             == identifier,
                        CompteLocal.identifiant_national == identifier,
                    )
                )
            )
        )
        return result.scalar_one_or_none()

    async def _get_profil_actif_du_compte(
        self, compte_id: UUID
    ) -> Optional[ProfilLocal]:
        """Récupère le premier profil actif d'un compte (profil principal)."""
        result = await self.db.execute(
            select(ProfilLocal).where(
                and_(
                    ProfilLocal.compte_id  == compte_id,
                    ProfilLocal.statut.in_(["actif", "bootstrap"]),
                    ProfilLocal.is_deleted == False,
                )
            ).order_by(ProfilLocal.created_at).limit(1)
        )
        return result.scalar_one_or_none()
