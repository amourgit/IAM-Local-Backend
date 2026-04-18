"""
Validateur unifié des tokens JWT.
Interface centralisée pour la validation de tous types de tokens.
"""

import logging
from datetime import datetime
from typing import Dict, Any, Optional, Tuple

from app.core.exceptions import TokenError
from .access_token_service import AccessTokenService
from .refresh_token_service import RefreshTokenService

logger = logging.getLogger(__name__)


class TokenValidator:
    """
    Validateur unifié pour tous les types de tokens JWT.
    Fournit une interface simple pour la validation.
    """

    def __init__(self):
        self.access_tokens = AccessTokenService()
        self.refresh_tokens = RefreshTokenService()

    async def validate_token(
        self,
        token: str,
        token_type: str = "auto"
    ) -> Tuple[str, Dict[str, Any]]:
        """
        Valide un token et retourne son type et payload.

        Args:
            token: Token JWT à valider
            token_type: Type attendu ("access", "refresh", "auto")

        Returns:
            Tuple: (token_type, payload)

        Raises:
            TokenError: Si le token est invalide
        """
        if token_type == "auto":
            token_type = self._detect_token_type(token)

        if token_type == "access":
            payload = self.access_tokens.validate_token(token)
            return "access", payload

        elif token_type == "refresh":
            payload = await self.refresh_tokens.validate_token(token)
            return "refresh", payload

        else:
            raise TokenError(f"Type de token non supporté: {token_type}")

    def validate_access_token(self, token: str) -> Dict[str, Any]:
        """
        Valide spécifiquement un token d'accès.
        """
        return self.access_tokens.validate_token(token)

    async def validate_refresh_token(self, token: str) -> Dict[str, Any]:
        """
        Valide spécifiquement un refresh token.
        """
        return await self.refresh_tokens.validate_token(token)

    def _detect_token_type(self, token: str) -> str:
        """
        Détecte automatiquement le type de token depuis son payload.
        """
        try:
            # Décodage sans validation pour inspection
            payload = self.access_tokens.decode_token_without_validation(token)

            if not payload:
                raise TokenError("Token malformé")

            token_type = payload.get("token_type")
            if token_type == "access":
                return "access"
            elif token_type == "refresh":
                return "refresh"
            else:
                raise TokenError(f"Type de token inconnu: {token_type}")

        except Exception as e:
            raise TokenError(f"Impossible de détecter le type de token: {str(e)}")

    # ── Validation Avancée ───────────────────────────────────────────

    def validate_token_structure(self, token: str) -> Dict[str, Any]:
        """
        Valide la structure d'un token sans vérifier la signature.
        Utile pour le debug et l'inspection.
        """
        payload = self.access_tokens.decode_token_without_validation(token)

        if not payload:
            return {"valid": False, "error": "Token malformé"}

        # Vérifications structurelles
        required_claims = ["iss", "sub", "iat", "exp"]
        missing_claims = [claim for claim in required_claims if claim not in payload]

        if missing_claims:
            return {
                "valid": False,
                "error": f"Claims manquants: {missing_claims}",
                "payload": payload
            }

        # Vérifications temporelles
        now = datetime.utcnow().timestamp()
        iat = payload.get("iat", 0)
        exp = payload.get("exp", 0)

        time_checks = {
            "issued_in_future": iat > now + 300,  # 5min de tolérance
            "expired": exp < now,
            "expires_soon": exp < now + 300,  # Expire dans 5min
        }

        return {
            "valid": True,
            "token_type": payload.get("token_type"),
            "issuer": payload.get("iss"),
            "subject": payload.get("sub"),
            "issued_at": datetime.utcfromtimestamp(iat).isoformat() if iat else None,
            "expires_at": datetime.utcfromtimestamp(exp).isoformat() if exp else None,
            "time_checks": time_checks,
            "payload": payload
        }

    def is_token_expired(self, token: str) -> bool:
        """
        Vérifie si un token est expiré.
        """
        structure = self.validate_token_structure(token)
        if not structure["valid"]:
            return True

        return structure["time_checks"]["expired"]

    def get_token_expiration_info(self, token: str) -> Dict[str, Any]:
        """
        Informations détaillées sur l'expiration d'un token.
        """
        structure = self.validate_token_structure(token)

        if not structure["valid"]:
            return {"error": structure.get("error")}

        time_checks = structure["time_checks"]
        expires_at = structure["expires_at"]

        if expires_at:
            expires_dt = datetime.fromisoformat(expires_at)
            now = datetime.utcnow()
            remaining_seconds = int((expires_dt - now).total_seconds())

            return {
                "expires_at": expires_at,
                "remaining_seconds": max(0, remaining_seconds),
                "remaining_minutes": max(0, remaining_seconds // 60),
                "remaining_hours": max(0, remaining_seconds // 3600),
                "is_expired": time_checks["expired"],
                "expires_soon": time_checks["expires_soon"],
                "issued_in_future": time_checks["issued_in_future"]
            }

        return {"error": "Date d'expiration manquante"}

    # ── Utilitaires ──────────────────────────────────────────────────

    def get_token_info(self, token: str) -> Dict[str, Any]:
        """
        Informations complètes sur un token (debug).
        """
        structure = self.validate_token_structure(token)

        if not structure["valid"]:
            return {"valid": False, "error": structure["error"]}

        payload = structure["payload"]

        return {
            "valid": True,
            "token_type": payload.get("token_type"),
            "issuer": payload.get("iss"),
            "subject": payload.get("sub"),
            "session_id": payload.get("session_id"),
            "permissions": payload.get("permissions", []),
            "roles": payload.get("roles", []),
            "type_profil": payload.get("type_profil"),
            "is_admin": payload.get("is_admin", False),
            "issued_at": structure["issued_at"],
            "expires_at": structure["expires_at"],
            "time_checks": structure["time_checks"],
            "version": payload.get("version", "unknown")
        }

    def compare_tokens(self, token1: str, token2: str) -> Dict[str, Any]:
        """
        Compare deux tokens pour détecter les différences.
        Utile pour le debug de refresh tokens.
        """
        info1 = self.get_token_info(token1)
        info2 = self.get_token_info(token2)

        differences = {}
        for key in set(info1.keys()) | set(info2.keys()):
            val1 = info1.get(key)
            val2 = info2.get(key)
            if val1 != val2:
                differences[key] = {"token1": val1, "token2": val2}

        return {
            "has_differences": len(differences) > 0,
            "differences": differences,
            "token1_valid": info1["valid"],
            "token2_valid": info2["valid"]
        }

    # ── Validation par Contexte ──────────────────────────────────────

    def validate_for_endpoint(
        self,
        token: str,
        required_permissions: list = None,
        required_roles: list = None,
        allow_admin: bool = True
    ) -> Dict[str, Any]:
        """
        Valide un token dans le contexte d'un endpoint protégé.
        Vérifie permissions, rôles, et droits admin.
        """
        try:
            payload = self.access_tokens.validate_token(token)

            user_permissions = set(payload.get("permissions", []))
            user_roles = set(payload.get("roles", []))
            is_admin = payload.get("is_admin", False)

            # Vérification permissions
            perm_check = self._check_permissions(
                user_permissions,
                required_permissions or []
            )

            # Vérification rôles
            role_check = self._check_roles(
                user_roles,
                required_roles or []
            )

            # Vérification admin
            admin_check = allow_admin and is_admin

            # Autorisation finale
            authorized = perm_check["granted"] or role_check["granted"] or admin_check

            return {
                "authorized": authorized,
                "user_id": payload.get("sub"),
                "session_id": payload.get("session_id"),
                "permissions": {
                    "required": required_permissions,
                    "user_has": list(user_permissions),
                    "check": perm_check
                },
                "roles": {
                    "required": required_roles,
                    "user_has": list(user_roles),
                    "check": role_check
                },
                "admin": {
                    "is_admin": is_admin,
                    "bypasses_checks": admin_check
                }
            }

        except TokenError as e:
            return {
                "authorized": False,
                "error": str(e),
                "error_type": "token_validation"
            }

    def _check_permissions(
        self,
        user_permissions: set,
        required_permissions: list
    ) -> Dict[str, Any]:
        """
        Vérifie si l'utilisateur a les permissions requises.
        Logique: AU MOINS UNE permission requise doit être présente.
        """
        if not required_permissions:
            return {"granted": True, "reason": "Aucune permission requise"}

        granted_permissions = user_permissions & set(required_permissions)

        return {
            "granted": len(granted_permissions) > 0,
            "required": required_permissions,
            "granted_permissions": list(granted_permissions),
            "missing_permissions": list(set(required_permissions) - granted_permissions)
        }

    def _check_roles(
        self,
        user_roles: set,
        required_roles: list
    ) -> Dict[str, Any]:
        """
        Vérifie si l'utilisateur a les rôles requis.
        Logique: AU MOINS UN rôle requis doit être présent.
        """
        if not required_roles:
            return {"granted": True, "reason": "Aucun rôle requis"}

        granted_roles = user_roles & set(required_roles)

        return {
            "granted": len(granted_roles) > 0,
            "required": required_roles,
            "granted_roles": list(granted_roles),
            "missing_roles": list(set(required_roles) - granted_roles)
        }