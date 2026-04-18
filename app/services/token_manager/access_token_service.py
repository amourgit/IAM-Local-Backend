"""
Service de gestion des tokens d'accès JWT.
Gère la création, validation et parsing des access tokens.
"""
import time
import jwt
import logging
from datetime import datetime
from typing import Dict, Any, Optional, List
from uuid import UUID

from app.config import settings
from app.core.exceptions import TokenError

logger = logging.getLogger(__name__)


class AccessTokenService:

    def __init__(self):
        self.secret_key    = settings.JWT_SECRET_KEY
        self.algorithm     = settings.JWT_ALGORITHM
        self.expire_minutes = settings.ACCESS_TOKEN_EXPIRE_MINUTES

    def create_token(
        self,
        user_id         : UUID,
        session_id      : UUID,
        permissions     : List[str] = None,   # UUIDs
        permission_codes: List[str] = None,   # codes lisibles (debug/logs)
        roles           : List[str] = None,
        type_profil     : str = None,
        is_admin        : bool = False,
        custom_claims   : Dict[str, Any] = None,
        expires_minutes : int = None,
    ) -> str:
        now_ts    = int(time.time())
        lifetime  = expires_minutes if expires_minutes is not None else self.expire_minutes
        expire_ts = now_ts + (lifetime * 60)

        payload = {
            "iss"              : "iam-local",
            "sub"              : str(user_id),
            "iat"              : now_ts,
            "exp"              : expire_ts,
            "jti"              : str(session_id),
            "session_id"       : str(session_id),
            "type_profil"      : type_profil,
            "permissions"      : permissions or [],        # UUIDs — pour vérification
            "permission_codes" : permission_codes or [],   # codes — pour debug/logs
            "roles"            : roles or [],
            "is_admin"         : is_admin,
            "token_type"       : "access",
            "version"          : "1.0",
        }

        if custom_claims:
            payload.update(custom_claims)

        try:
            token = jwt.encode(payload, self.secret_key, algorithm=self.algorithm)
            logger.debug(f"Access token créé pour user {user_id}, session {session_id}")
            return token
        except Exception as e:
            logger.error(f"Erreur création access token: {str(e)}")
            raise TokenError("Erreur lors de la création du token d'accès")

    def validate_token(self, token: str) -> Dict[str, Any]:
        try:
            payload = jwt.decode(
                token,
                self.secret_key,
                algorithms=[self.algorithm],
                options={
                    "verify_signature" : True,
                    "verify_exp"       : True,
                    "verify_iat"       : True,
                    "verify_iss"       : True,
                    "require"          : ["iss", "sub", "exp", "session_id"]
                }
            )

            if payload.get("iss") != "iam-local":
                raise TokenError("Issuer invalide")

            if payload.get("token_type") != "access":
                raise TokenError("Type de token invalide")

            if payload.get("exp") and payload["exp"] < time.time():
                raise TokenError("Token expiré")

            logger.debug(f"Access token validé pour user {payload.get('sub')}")
            return payload

        except jwt.ExpiredSignatureError:
            raise TokenError("Token d'accès expiré")
        except jwt.InvalidSignatureError:
            raise TokenError("Signature du token invalide")
        except jwt.InvalidIssuerError:
            raise TokenError("Émetteur du token invalide")
        except jwt.InvalidTokenError as e:
            raise TokenError(f"Token d'accès invalide: {str(e)}")
        except Exception as e:
            logger.error(f"Erreur validation access token: {str(e)}")
            raise TokenError("Erreur lors de la validation du token d'accès")

    def decode_token_without_validation(self, token: str) -> Optional[Dict[str, Any]]:
        try:
            return jwt.decode(token, options={"verify_signature": False})
        except Exception:
            return None

    def get_token_expiration(self, token: str) -> Optional[datetime]:
        payload = self.decode_token_without_validation(token)
        if payload and "exp" in payload:
            return datetime.utcfromtimestamp(payload["exp"])
        return None

    def is_token_expired(self, token: str) -> bool:
        expiration = self.get_token_expiration(token)
        return expiration is None or expiration < datetime.utcnow()

    def get_token_info(self, token: str) -> Dict[str, Any]:
        payload = self.decode_token_without_validation(token)
        if not payload:
            return {"valid": False}
        return {
            "valid"             : True,
            "user_id"           : payload.get("sub"),
            "session_id"        : payload.get("session_id"),
            "type_profil"       : payload.get("type_profil"),
            "permissions_count" : len(payload.get("permissions", [])),
            "roles_count"       : len(payload.get("roles", [])),
            "issued_at"         : datetime.utcfromtimestamp(payload["iat"]) if payload.get("iat") else None,
            "expires_at"        : datetime.utcfromtimestamp(payload["exp"]) if payload.get("exp") else None,
            "is_expired"        : self.is_token_expired(token),
            "issuer"            : payload.get("iss"),
            "token_type"        : payload.get("token_type"),
        }

    @property
    def token_lifetime_seconds(self) -> int:
        return self.expire_minutes * 60
