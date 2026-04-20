import asyncio
import logging
from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import text

from app.database import engine
from app.middleware.audit import AuditMiddleware
from app.middleware.logging import setup_logging
from app.middleware.permission_middleware import PermissionMiddleware
from app.api.v1.router import router as api_v1_router
from app.config import settings
from app.infrastructure.kafka.producer import KafkaProducer
from app.infrastructure.kafka.consumer import KafkaConsumer

logger = logging.getLogger(__name__)


async def _run_seed_sync(db) -> None:
    """
    Synchronise iam_seed.json → DB à chaque démarrage.

    Règle fondamentale :
    - JSON présent, DB absente  → INSERT (nouveau élément ajouté dans le JSON)
    - JSON présent, DB présente → SKIP   (idempotent)
    - DB présente, JSON absent  → SKIP   (créé via API, on ne touche pas)

    Erreur de chargement → log + continue (le serveur ne crashe PAS).
    """
    try:
        from seeds.seed_loader import SeedLoader
        loader  = SeedLoader(db)
        rapport = await loader.run()

        total_new = (
            rapport["permissions"]["ajoutees"]
            + rapport["roles"]["ajoutes"]
            + rapport["groupes"]["ajoutes"]
            + rapport["endpoints"]["ajoutes"]
        )

        if not rapport["ok"] and rapport["erreurs"]:
            logger.warning(
                f"SeedSync: terminé avec {len(rapport['erreurs'])} avertissement(s). "
                "Le serveur continue normalement."
            )

        if total_new > 0:
            await db.commit()
            logger.info(f"SeedSync: {total_new} élément(s) synchronisé(s) depuis iam_seed.json")
        else:
            logger.info("SeedSync: aucun changement détecté")

    except Exception as e:
        # Le SeedLoader ne devrait jamais lever — mais on est paranoïaque
        logger.error(
            f"SeedSync: erreur inattendue — {e}. "
            "Le serveur continue normalement sans synchronisation."
        )
        try:
            await db.rollback()
        except Exception:
            pass


async def _run_bootstrap(db) -> None:
    """
    Bootstrap initial (une seule fois) : crée le profil admin temporaire.
    Idempotent : ne fait rien si déjà effectué.
    """
    try:
        from seeds.bootstrap import BootstrapService
        service = BootstrapService(db)
        rapport = await service.run()

        if not rapport["deja_fait"] and rapport.get("token"):
            import json
            from pathlib import Path
            creds_path = Path("bootstrap_credentials.json")
            with open(creds_path, "w") as f:
                json.dump({
                    "profil_id" : rapport["profil_bootstrap"],
                    "token"     : rapport["token"],
                    "expires_in": "48h",
                    "warning"   : (
                        "TOKEN PRIVILÉGIÉ — "
                        "SUPPRIMER CE FICHIER APRÈS USAGE"
                    ),
                }, f, indent=2)
            logger.warning(
                "🔐 BOOTSTRAP — bootstrap_credentials.json généré. "
                "Créez l'admin réel puis supprimez ce fichier."
            )

    except Exception as e:
        logger.error(f"Bootstrap: erreur (non bloquant) — {e}")


@asynccontextmanager
async def lifespan(app: FastAPI):
    # ── Startup ───────────────────────────────────────────
    setup_logging(debug=settings.DEBUG)

    # Vérification DB
    async with engine.connect() as conn:
        await conn.execute(text("SELECT 1"))

    logger.info(
        f"Module 02 — IAM Local démarré [{settings.ETABLISSEMENT_CODE}]"
    )

    # Démarrer le Kafka consumer en arrière-plan
    kafka_consumer = KafkaConsumer()
    consumer_task  = asyncio.create_task(kafka_consumer.start())
    app.state.kafka_consumer = kafka_consumer
    app.state.consumer_task  = consumer_task
    logger.info("Kafka consumer démarré")

    # ── Séquence de démarrage ─────────────────────────────────
    from app.database import AsyncSessionLocal

    # ÉTAPE 1 : Synchronisation seeds (à chaque démarrage)
    async with AsyncSessionLocal() as db:
        await _run_seed_sync(db)

    # ÉTAPE 2 : Bootstrap profil admin (une seule fois)
    async with AsyncSessionLocal() as db:
        await _run_bootstrap(db)

    yield

    # ── Shutdown ──────────────────────────────────────────
    await kafka_consumer.stop()
    KafkaProducer().flush()
    await engine.dispose()


app = FastAPI(
    title       = "Module 02 — IAM Local",
    description = (
        "Identity & Access Management Local. "
        "Gestion des profils, rôles, permissions, "
        "groupes, délégations et habilitations "
        "pour un établissement EGEN."
    ),
    version  = "1.0.0",
    docs_url = "/docs",
    redoc_url= "/redoc",
    lifespan = lifespan,
)

# ── Middlewares ───────────────────────────────────────────
# Ordre important : le dernier ajouté est le premier exécuté

app.add_middleware(PermissionMiddleware)
app.add_middleware(AuditMiddleware)
app.add_middleware(
    CORSMiddleware,
    allow_origins     = ["*"],
    allow_credentials = True,
    allow_methods     = ["*"],
    allow_headers     = ["*"],
)

app.include_router(api_v1_router, prefix="/api/v1")


@app.get("/health", tags=["Système"])
async def health():
    return {
        "status"       : "ok",
        "service"      : "module-02-iam-local",
        "version"      : "1.0.0",
        "etablissement": settings.ETABLISSEMENT_CODE,
    }
