"""
Script CLI de bootstrap IAM Local.
À exécuter immédiatement après `alembic upgrade head`.

Usage:
    python seeds/scripts/run_bootstrap.py

Options:
    --force   Forcer le re-bootstrap même si déjà effectué
    --token   Afficher uniquement le token (pour scripts)
"""
import asyncio
import argparse
import json
import sys
import logging
from datetime import datetime
from pathlib import Path

# Ajouter le projet au path
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from app.database import AsyncSessionLocal
from app.middleware.logging import setup_logging
from seeds.bootstrap import BootstrapService

CREDENTIALS_FILE = Path(__file__).parent.parent.parent / "bootstrap_credentials.json"


async def run(force: bool = False, token_only: bool = False):
    setup_logging(debug=False)
    logger = logging.getLogger(__name__)

    async with AsyncSessionLocal() as db:
        service = BootstrapService(db)

        if force:
            logger.warning("⚠️  Mode --force activé")

        rapport = await service.run()

    if token_only:
        print(rapport.get("token", ""))
        return

    if not rapport["token"]:
        print("\n✅ Bootstrap déjà effectué. Système opérationnel.")
        if rapport.get("profil_bootstrap"):
            print(
                f"⚠️  Profil bootstrap encore actif : "
                f"{rapport['profil_bootstrap']}"
            )
            print("   → Créez l'admin réel et supprimez ce profil.")
        return

    # Écrire credentials
    credentials = {
        "generated_at"     : datetime.utcnow().isoformat(),
        "profil_id"        : rapport["profil_bootstrap"],
        "token"            : rapport["token"],
        "expires_in_hours" : 48,
        "permissions"      : [
            "iam.profil.creer",
            "iam.profil.consulter",
            "iam.profil.modifier",
            "iam.role.consulter",
            "iam.role.assigner",
            "iam.groupe.consulter",
            "iam.groupe.membre.ajouter",
        ],
        "instructions": {
            "step_1": "Utilisez ce token pour créer le profil admin réel",
            "step_2": "POST /api/v1/profils/ avec les données de l'admin",
            "step_3": "POST /api/v1/profils/{id}/roles avec role iam.admin",
            "step_4": "POST /api/v1/groupes/{super_admin_id}/membres",
            "step_5": "Vérifiez la connexion de l'admin réel",
            "step_6": f"DELETE /api/v1/profils/{rapport['profil_bootstrap']}",
        },
        "warning": (
            "CE FICHIER CONTIENT UN TOKEN PRIVILÉGIÉ. "
            "SUPPRIMEZ-LE APRÈS UTILISATION. "
            "NE PAS COMMITTER."
        ),
    }

    with open(CREDENTIALS_FILE, "w") as f:
        json.dump(credentials, f, indent=2)

    # Affichage console
    print("\n" + "=" * 65)
    print("  BOOTSTRAP IAM LOCAL — INSTALLATION TERMINÉE")
    print("=" * 65)
    print(f"\n  Permissions créées  : {rapport['permissions']['crees']}")
    print(f"  Rôles créés         : {rapport['roles']['crees']}")
    print(f"  Groupes créés       : {rapport['groupes']['crees']}")
    print(f"\n  Profil bootstrap ID : {rapport['profil_bootstrap']}")
    print(f"\n  Token (valide 48h)  :")
    print(f"\n  {rapport['token']}\n")
    print(f"  Credentials sauvés  : bootstrap_credentials.json")
    print("\n" + "=" * 65)
    print("\n  ⚠️  ÉTAPES SUIVANTES :")
    print("  1. Utilisez le token pour créer votre profil admin réel")
    print("  2. POST /api/v1/profils/")
    print("  3. Assignez le rôle iam.admin")
    print("  4. Supprimez le profil bootstrap")
    print(f"     DELETE /api/v1/profils/{rapport['profil_bootstrap']}")
    print("  5. Supprimez bootstrap_credentials.json")
    print("\n" + "=" * 65 + "\n")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Bootstrap IAM Local"
    )
    parser.add_argument(
        "--force",
        action  = "store_true",
        help    = "Forcer même si déjà effectué",
    )
    parser.add_argument(
        "--token",
        action  = "store_true",
        help    = "Afficher uniquement le token",
    )
    args = parser.parse_args()
    asyncio.run(run(force=args.force, token_only=args.token))
