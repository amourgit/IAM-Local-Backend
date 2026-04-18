"""
Registre des modules métier connus par IAM Local.
Chaque module a un code, un nom et une URL de base.

Pour ajouter un nouveau module :
1. Ajouter son URL dans .env  ex: SCOLARITE_URL=http://localhost:8003
2. Ajouter son entrée dans MODULE_REGISTRY ci-dessous
C'est tout — le gateway s'en charge automatiquement.
"""

from typing import Optional
from app.config import settings


# ── Registre central des modules ─────────────────────────────────────
# Structure : { "code_module": "http://host:port" }
#
# Convention URL :
#   - Dev  : http://localhost:PORT
#   - Prod : http://nom-service:PORT  (nom Docker Compose)
#
# Pour rendre configurable via env :
#   getattr(settings, "SCOLARITE_URL", "http://localhost:8003")
#   → Si SCOLARITE_URL est dans .env → utilisé
#   → Sinon → fallback sur la valeur par défaut

MODULE_REGISTRY: dict[str, str] = {
    "referentiel_organisationnel": getattr(settings, "REFERENTIEL_URL", "http://localhost:8001"),
    "scolarite"   : getattr(settings, "SCOLARITE_URL",    "http://localhost:8003"),
    "notes"       : getattr(settings, "NOTES_URL",        "http://localhost:8004"),
    "rh"          : getattr(settings, "RH_URL",           "http://localhost:8005"),
    "finances"    : getattr(settings, "FINANCES_URL",     "http://localhost:8006"),
    "bibliotheque": getattr(settings, "BIBLIOTHEQUE_URL", "http://localhost:8007"),
}


def get_module_url(module_code: str) -> Optional[str]:
    """
    Retourne l'URL de base d'un module par son code.
    Retourne None si le module est inconnu.
    """
    return MODULE_REGISTRY.get(module_code.lower())


def get_all_modules() -> dict[str, str]:
    """Retourne tous les modules enregistrés."""
    return MODULE_REGISTRY.copy()


def is_module_known(module_code: str) -> bool:
    """Vérifie si un module est connu du registry."""
    return module_code.lower() in MODULE_REGISTRY
