import logging
from uuid import UUID
from typing import Optional
from fastapi import Request, Depends
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
import jwt
from app.config import settings
from app.core.exceptions import TokenError, UnauthorizedError

logger   = logging.getLogger(__name__)
security = HTTPBearer(auto_error=False)


class CurrentUser:
    def __init__(
        self,
        profil_id        : UUID,
        user_id_national : Optional[UUID],
        type_profil      : str,
        statut           : str,
        permissions      : list[str],       # UUIDs — pour vérification middleware
        permission_codes : list[str],       # codes — pour require_permission()
        roles            : list[str],
        token            : str = "",
        is_bootstrap     : bool = False,
    ):
        self.profil_id        = profil_id
        self.user_id_national = user_id_national
        self.type_profil      = type_profil
        self.statut           = statut
        self.permissions      = permissions
        self.permission_codes = permission_codes
        self.roles            = roles
        self.token            = token
        self.is_bootstrap     = is_bootstrap

    def has_permission(self, code: str) -> bool:
        """Vérifie par code — immuable et lisible."""
        return code in self.permission_codes

    def has_any_permission(self, *codes: str) -> bool:
        """Vérifie si au moins un code est présent."""
        return any(c in self.permission_codes for c in codes)

    def is_admin(self) -> bool:
        """
        iam.admin bypass total.
        Bootstrap ne bypass jamais — limité par ses permissions.
        """
        if self.is_bootstrap:
            return False
        return "iam.admin" in self.roles


async def _verifier_blacklist(profil_id: UUID) -> bool:
    """Vérifie si un profil est blacklisté dans Redis."""
    try:
        from app.infrastructure.cache.redis import CacheService
        cache  = CacheService()
        result = await cache.get(f"iam:blacklist:profil:{profil_id}")
        return result is not None and result.get("blacklisted", False)
    except Exception:
        return False


async def get_current_user(
    request     : Request,
    credentials : Optional[HTTPAuthorizationCredentials] = Depends(security),
) -> CurrentUser:
    if not credentials:
        raise UnauthorizedError("Token de session manquant.")

    token = credentials.credentials

    try:
        payload = jwt.decode(
            token,
            settings.JWT_SECRET_KEY,
            algorithms = [settings.JWT_ALGORITHM],
        )

        profil_id    = UUID(payload["sub"])
        is_bootstrap = payload.get("is_bootstrap", False)

        # Vérification blacklist Redis
        if await _verifier_blacklist(profil_id):
            raise TokenError(
                "Session invalide. "
                "Ce compte a été désactivé. "
                "Veuillez vous connecter avec votre compte réel."
            )

        return CurrentUser(
            profil_id        = profil_id,
            user_id_national = (
                UUID(payload["user_id_national"])
                if payload.get("user_id_national")
                else None
            ),
            type_profil      = payload.get("type_profil", "invite"),
            statut           = payload.get("statut", "actif"),
            permissions      = payload.get("permissions", []),       # UUIDs
            permission_codes = payload.get("permission_codes", []),  # codes
            roles            = payload.get("roles", []),
            token            = token,
            is_bootstrap     = is_bootstrap,
        )

    except jwt.ExpiredSignatureError:
        raise TokenError("Session expirée. Veuillez vous reconnecter.")
    except jwt.InvalidTokenError as e:
        raise TokenError(f"Token invalide : {e}")
    except (KeyError, ValueError) as e:
        raise TokenError(f"Token incomplet : {e}")


async def get_current_user_optional(
    request     : Request,
    credentials : Optional[HTTPAuthorizationCredentials] = Depends(security),
) -> Optional[CurrentUser]:
    if not credentials:
        return None
    try:
        return await get_current_user(request, credentials)
    except Exception:
        return None


def require_permission(permission: str):
    """Vérifie un code de permission. Admin bypass. Bootstrap limité."""
    async def checker(
        user: CurrentUser = Depends(get_current_user),
    ) -> CurrentUser:
        from app.core.exceptions import PermissionDeniedError
        if not user.is_admin() and not user.has_permission(permission):
            raise PermissionDeniedError(permission)
        return user
    return checker


def require_any_permission(*permissions: str):
    """Vérifie qu'au moins un code est présent. Admin bypass."""
    async def checker(
        user: CurrentUser = Depends(get_current_user),
    ) -> CurrentUser:
        from app.core.exceptions import PermissionDeniedError
        if not user.is_admin() and not user.has_any_permission(*permissions):
            raise PermissionDeniedError(
                f"Une des permissions requises : {list(permissions)}"
            )
        return user
    return checker


def require_not_bootstrap():
    """Bloque explicitement les profils bootstrap sur les routes sensibles."""
    async def checker(
        user: CurrentUser = Depends(get_current_user),
    ) -> CurrentUser:
        from app.core.exceptions import ForbiddenError
        if user.is_bootstrap:
            raise ForbiddenError(
                "Ce compte bootstrap est limité à la création "
                "du premier administrateur réel. "
                "Action non autorisée."
            )
        return user
    return checker
