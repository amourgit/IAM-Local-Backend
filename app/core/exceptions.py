from fastapi import HTTPException, status


class NotFoundError(HTTPException):
    def __init__(self, entite: str, identifiant: str):
        super().__init__(
            status_code = status.HTTP_404_NOT_FOUND,
            detail      = f"{entite} introuvable : {identifiant}",
        )


class AlreadyExistsError(HTTPException):
    def __init__(self, entite: str, champ: str, valeur: str):
        super().__init__(
            status_code = status.HTTP_409_CONFLICT,
            detail      = f"{entite} existe déjà avec {champ}={valeur}",
        )


class ValidationError(HTTPException):
    def __init__(self, message: str):
        super().__init__(
            status_code = status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail      = message,
        )


class ForbiddenError(HTTPException):
    def __init__(self, message: str = "Accès refusé."):
        super().__init__(
            status_code = status.HTTP_403_FORBIDDEN,
            detail      = message,
        )


class UnauthorizedError(HTTPException):
    def __init__(self, message: str = "Authentification requise."):
        super().__init__(
            status_code = status.HTTP_401_UNAUTHORIZED,
            detail      = message,
        )


class AuthenticationError(HTTPException):
    def __init__(self, message: str = "Authentification échouée."):
        super().__init__(
            status_code = status.HTTP_401_UNAUTHORIZED,
            detail      = message,
        )


class DependencyError(HTTPException):
    def __init__(self, entite: str, dependance: str):
        super().__init__(
            status_code = status.HTTP_409_CONFLICT,
            detail      = (
                f"Impossible de supprimer {entite} : "
                f"des {dependance} y sont rattachés."
            ),
        )


class TokenError(HTTPException):
    def __init__(self, message: str = "Token invalide."):
        super().__init__(
            status_code = status.HTTP_401_UNAUTHORIZED,
            detail      = message,
            headers     = {"WWW-Authenticate": "Bearer"},
        )


class PermissionDeniedError(HTTPException):
    def __init__(self, permission: str, perimetre: dict = None):
        detail = f"Permission requise : {permission}"
        if perimetre:
            detail += f" sur périmètre {perimetre}"
        super().__init__(
            status_code = status.HTTP_403_FORBIDDEN,
            detail      = detail,
        )
