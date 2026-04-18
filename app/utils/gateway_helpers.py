"""
Utilitaires pour le Gateway et la gestion des endpoints.
"""
from typing import Dict, Optional
from app.config import settings


# Configuration du routage des modules
MODULE_ROUTES: Dict[str, str] = {
    "scolarite": getattr(settings, "SCOLARITE_URL", "http://scolarite:8003"),
    "pedagogie": getattr(settings, "PEDAGOGIE_URL", "http://pedagogie:8004"),
    "examens": getattr(settings, "EXAMENS_URL", "http://examens:8005"),
    "enseignants": getattr(settings, "ENSEIGNANTS_URL", "http://enseignants:8006"),
    "referentiel": getattr(settings, "REFERENTIEL_URL", "http://referentiel:8007"),
}


def get_module_url(module_code: str) -> Optional[str]:
    """Récupère l'URL interne d'un module."""
    return MODULE_ROUTES.get(module_code)


def extract_module_from_path(path: str) -> Optional[str]:
    """
    Extrait le code du module du chemin de l'API.
    
    Exemples :
    - /api/v1/scolarite/inscriptions → "scolarite"
    - /api/v1/pedagogie/cours → "pedagogie"
    """
    parts = path.lstrip("/").split("/")
    if len(parts) < 2:
        return None
    
    # structure : api/v1/MODULE/...
    if parts[0] == "api" and parts[1] == "v1" and len(parts) >= 3:
        return parts[2]
    
    return None


def is_internal_path(path: str) -> bool:
    """Vérifie si le chemin est interne à IAM Local (non proxifié)."""
    internal_prefixes = [
        "/docs",
        "/redoc",
        "/openapi.json",
        "/health",
        "/api/v1/auth",
        "/api/v1/tokens",
        "/api/v1/endpoints",
        "/api/v1/permissions",
        "/api/v1/roles",
        "/api/v1/groupes",
        "/api/v1/profils",
        "/api/v1/habilitations",
        "/api/v1/audit",
        "/api/v1/admin",
    ]
    return any(path.startswith(prefix) for prefix in internal_prefixes)

