from uuid import UUID
from typing import Optional, Any
from datetime import datetime, timezone
from sqlalchemy.ext.asyncio import AsyncSession
from app.repositories.journal_acces import JournalAccesRepository
from app.core.enums import TypeAction


class AuditService:
    """
    Service de journalisation exhaustive.
    Appelé par tous les autres services pour
    tracer chaque action significative.
    Jamais bloquant — les erreurs sont loguées
    sans faire planter la requête principale.
    """

    def __init__(self, db: AsyncSession):
        self.repo = JournalAccesRepository(db)

    async def log(
        self,
        type_action      : str,
        profil_id        : Optional[UUID]  = None,
        user_id_national : Optional[UUID]  = None,
        nom_affiche      : Optional[str]   = None,
        module           : Optional[str]   = None,
        ressource        : Optional[str]   = None,
        action           : Optional[str]   = None,
        ressource_id     : Optional[str]   = None,
        permission_verifiee : Optional[str] = None,
        perimetre_verifie   : Optional[Any] = None,
        autorise         : Optional[bool]  = None,
        raison           : Optional[str]   = None,
        ip_address       : Optional[str]   = None,
        user_agent       : Optional[str]   = None,
        request_id       : Optional[str]   = None,
        session_id       : Optional[str]   = None,
        details          : Optional[Any]   = None,
    ) -> None:
        try:
            await self.repo.create({
                "type_action"         : type_action,
                "profil_id"           : profil_id,
                "user_id_national"    : user_id_national,
                "nom_affiche"         : nom_affiche,
                "module"              : module,
                "ressource"           : ressource,
                "action"              : action,
                "ressource_id"        : ressource_id,
                "permission_verifiee" : permission_verifiee,
                "perimetre_verifie"   : perimetre_verifie,
                "autorise"            : autorise,
                "raison"              : raison,
                "ip_address"          : ip_address,
                "user_agent"          : user_agent,
                "request_id"          : request_id,
                "session_id"          : session_id,
                "details"             : details,
                "timestamp"           : datetime.now(timezone.utc),
            })
        except Exception as e:
            import logging
            logging.getLogger(__name__).error(
                f"Audit log failed — type={type_action} error={e}"
            )

    async def log_connexion(
        self,
        user_id_national : UUID,
        profil_id        : Optional[UUID],
        nom_affiche      : str,
        ip_address       : Optional[str] = None,
        user_agent       : Optional[str] = None,
        request_id       : Optional[str] = None,
    ) -> None:
        await self.log(
            type_action      = TypeAction.CONNEXION,
            profil_id        = profil_id,
            user_id_national = user_id_national,
            nom_affiche      = nom_affiche,
            module           = "auth",
            ressource        = "session",
            action           = "connexion",
            autorise         = True,
            ip_address       = ip_address,
            user_agent       = user_agent,
            request_id       = request_id,
        )

    async def log_echec_auth(
        self,
        user_id_national : Optional[UUID],
        raison           : str,
        ip_address       : Optional[str] = None,
        request_id       : Optional[str] = None,
    ) -> None:
        await self.log(
            type_action      = TypeAction.ECHEC_AUTH,
            user_id_national = user_id_national,
            module           = "auth",
            ressource        = "session",
            action           = "connexion",
            autorise         = False,
            raison           = raison,
            ip_address       = ip_address,
            request_id       = request_id,
        )

    async def log_verification_permission(
        self,
        profil_id           : UUID,
        user_id_national    : UUID,
        permission          : str,
        perimetre           : Optional[Any],
        autorise            : bool,
        raison              : Optional[str] = None,
        request_id          : Optional[str] = None,
    ) -> None:
        type_action = (
            TypeAction.ACCES_AUTORISE
            if autorise
            else TypeAction.ACCES_REFUSE
        )
        await self.log(
            type_action         = type_action,
            profil_id           = profil_id,
            user_id_national    = user_id_national,
            permission_verifiee = permission,
            perimetre_verifie   = perimetre,
            autorise            = autorise,
            raison              = raison,
            request_id          = request_id,
        )

    async def log_assignation_role(
        self,
        profil_id        : UUID,
        role_code        : str,
        assigne_par      : UUID,
        perimetre        : Optional[Any] = None,
        request_id       : Optional[str] = None,
    ) -> None:
        await self.log(
            type_action      = TypeAction.ROLE_ASSIGNE,
            profil_id        = profil_id,
            module           = "iam",
            ressource        = "assignation_role",
            action           = "assigner",
            autorise         = True,
            details          = {
                "role_code"   : role_code,
                "assigne_par" : str(assigne_par),
                "perimetre"   : perimetre,
            },
            request_id       = request_id,
        )

    async def log_revocation_role(
        self,
        profil_id        : UUID,
        role_code        : str,
        revoque_par      : UUID,
        raison           : str,
        request_id       : Optional[str] = None,
    ) -> None:
        await self.log(
            type_action      = TypeAction.ROLE_REVOQUE,
            profil_id        = profil_id,
            module           = "iam",
            ressource        = "assignation_role",
            action           = "revoquer",
            autorise         = True,
            raison           = raison,
            details          = {
                "role_code"  : role_code,
                "revoque_par": str(revoque_par),
            },
            request_id       = request_id,
        )
