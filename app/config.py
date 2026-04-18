from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    APP_NAME              : str = "module-02-iam-local"
    DEBUG                 : bool = False

    DATABASE_URL          : str
    REDIS_URL             : str = "redis://localhost:6379/2"
    KAFKA_BOOTSTRAP_SERVERS: str = "localhost:9092"

    IAM_CENTRAL_URL       : str = "http://localhost:8000"
    IAM_CENTRAL_JWKS_URL  : str = "http://localhost:8000/.well-known/jwks.json"
    IAM_CENTRAL_TOKEN     : str = ""  # Token service-to-service pour appels serveur

    JWT_SECRET_KEY        : str
    JWT_ALGORITHM         : str = "HS256"
    JWT_EXPIRE_MINUTES    : int = 480

    ETABLISSEMENT_ID      : str = ""
    ETABLISSEMENT_CODE    : str = ""

    # ── Configuration TokenManager ────────────────────────────────

    # Access Tokens
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 30  # 30 minutes

    # Refresh Tokens
    REFRESH_TOKEN_EXPIRE_DAYS: int = 30  # 30 jours

    # Sessions
    SESSION_TTL_HOURS: int = 24  # 24 heures
    MAX_SESSIONS_PER_USER: int = 5  # Maximum 5 sessions simultanées
    SESSION_BLACKLIST_TTL_MINUTES: int = 1440  # 24h de blacklist

    # Synchronisation IAM Central
    IAM_CENTRAL_ENABLED: bool = True
    IAM_CENTRAL_SYNC_TIMEOUT_SECONDS: int = 30
    IAM_CENTRAL_CACHE_TTL_MINUTES: int = 15  # Cache 15 minutes

    # Sécurité
    TOKEN_SIGNATURE_ALGORITHM: str = "HS256"
    ENCRYPT_TOKENS: bool = False  # Pour production, activer le chiffrement

    # Webhooks (optionnel)
    WEBHOOK_SECRET: str = ""

# ── URLs des modules métier (pour le Gateway) ─────────────────
    REFERENTIEL_URL : str = "http://localhost:8001"
    SCOLARITE_URL   : str = "http://localhost:8003"
    NOTES_URL       : str = "http://localhost:8004"
    RH_URL          : str = "http://localhost:8005"
    FINANCES_URL    : str = "http://localhost:8006"
    BIBLIOTHEQUE_URL: str = "http://localhost:8007"

    class Config:
        env_file = ".env"


settings = Settings()
