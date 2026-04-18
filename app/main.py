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

    # Bootstrap automatique après migration
    try:
        from app.database import AsyncSessionLocal
        from seeds.bootstrap import BootstrapService
        async with AsyncSessionLocal() as db:
            service = BootstrapService(db)
            rapport = await service.run()
            if not rapport["deja_fait"] and rapport["token"]:
                import json
                from pathlib import Path
                creds_path = Path("bootstrap_credentials.json")
                with open(creds_path, "w") as f:
                    json.dump({
                        "profil_id"  : rapport["profil_bootstrap"],
                        "token"      : rapport["token"],
                        "expires_in" : "48h",
                        "warning"    : (
                            "TOKEN PRIVILÉGIÉ — "
                            "SUPPRIMER CE FICHIER APRÈS USAGE"
                        ),
                    }, f, indent=2)
                logger.warning(
                    "🔐 BOOTSTRAP — credentials.json généré. "
                    "Créez l'admin réel puis supprimez ce fichier."
                )
    except Exception as e:
        logger.error(f"Bootstrap error (non bloquant) : {e}")

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

app.add_middleware(PermissionMiddleware)   # ✅ Nouveau — vérification permissions dynamique
app.add_middleware(AuditMiddleware)        # Audit des accès
# GatewayMiddleware retiré — remplacé par PermissionMiddleware
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
