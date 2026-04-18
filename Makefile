.PHONY: help install run migrate migrate-create seed bootstrap \
        setup-dev setup-prod \
        test lint format check-format clean \
        docker-dev docker-prod docker-down-dev docker-down-prod \
        docker-clean-dev docker-clean-prod

# ──────────────────────────────────────────────
#  AIDE
# ──────────────────────────────────────────────
help:
	@echo ""
	@echo "EGEN National Backend IAM Local — commandes disponibles"
	@echo ""
	@echo "── DÉPLOIEMENT (ordre à suivre) ────────────────────────"
	@echo "  make docker-dev      1. Démarrer PostgreSQL + Redis + Kafka (Docker)"
	@echo "  make install         2. Installer les dépendances Python"
	@echo "  make migrate         3. Appliquer toutes les migrations (schéma + seeds)"
	@echo "  make bootstrap       4. Créer le profil bootstrap (1ère fois seulement)"
	@echo "  make run             5. Démarrer l'API (port 8002)"
	@echo ""
	@echo "── DÉVELOPPEMENT ───────────────────────────────────────"
	@echo "  make setup-dev       Tout en une commande (docker + install + migrate + bootstrap)"
	@echo "  make migrate-create msg='description'  Créer une migration manuelle"
	@echo "  make test            Lancer les tests"
	@echo "  make lint            Vérifier le code (ruff)"
	@echo "  make format          Formater le code (ruff)"
	@echo ""
	@echo "── DOCKER ──────────────────────────────────────────────"
	@echo "  make docker-dev      Démarrer les services DEV"
	@echo "  make docker-prod     Démarrer les services PROD (avec build)"
	@echo "  make docker-down-dev Arrêter les services DEV"
	@echo "  make docker-clean-dev Arrêter + supprimer les volumes DEV"
	@echo ""

# ──────────────────────────────────────────────
#  INSTALLATION
# ──────────────────────────────────────────────
install:
	pip install -r requirements.txt
	pip install -e ".[dev]"

# ──────────────────────────────────────────────
#  MIGRATIONS
#  Applique uniquement les migrations Alembic
#  (schéma + seeds inclus dans les migrations)
#  Ne pas mélanger avec bootstrap
# ──────────────────────────────────────────────
migrate:
	@echo "📦 Application des migrations Alembic..."
	@alembic upgrade head
	@echo "✅ Migrations appliquées"

migrate-create:
	@alembic revision --autogenerate -m "$(msg)"
	@echo "✅ Migration créée — vérifiez migrations/versions/"

migrate-auto:
	@echo "🔍 Détection des changements de modèles..."
	@alembic revision --autogenerate -m "auto_migration_$(shell date +%Y%m%d_%H%M%S)"
	@echo "✅ Migration générée — relancez 'make migrate' pour l'appliquer"

# ──────────────────────────────────────────────
#  BOOTSTRAP
#  À exécuter UNE SEULE FOIS après migrate
#  Crée le profil bootstrap système
#  Idempotent — détecte si déjà fait
# ──────────────────────────────────────────────
bootstrap:
	@echo "🚀 Exécution du bootstrap IAM Local..."
	@python seeds/bootstrap.py
	@echo "✅ Bootstrap terminé"

# ──────────────────────────────────────────────
#  SETUP COMPLET — DÉPLOIEMENT DE ZÉRO
# ──────────────────────────────────────────────
setup-dev:
	@echo "🔧 Déploiement complet IAM Local (DEV)..."
	$(MAKE) docker-dev
	@echo "⏳ Attente démarrage services (10s)..."
	@sleep 10
	$(MAKE) install
	$(MAKE) migrate
	$(MAKE) bootstrap
	$(MAKE) run

# ──────────────────────────────────────────────
#  APPLICATION
# ──────────────────────────────────────────────
run:
	uvicorn app.main:app --host 0.0.0.0 --port 8002 --reload

run-prod:
	uvicorn app.main:app --host 0.0.0.0 --port 8002 --workers 4

# ──────────────────────────────────────────────
#  QUALITÉ CODE
# ──────────────────────────────────────────────
test:
	pytest app/tests/ -v --cov=app --cov-report=term-missing

lint:
	ruff check app/

format:
	ruff format app/
	ruff check --fix app/

check-format:
	ruff format --check app/
	ruff check app/

# ──────────────────────────────────────────────
#  DOCKER
# ──────────────────────────────────────────────
docker-dev:
	docker compose -f docker-compose-dev.yml up -d
	@echo "✅ Services DEV démarrés (PostgreSQL:5433, Redis:6379, Kafka:9092)"

docker-prod:
	docker compose -f docker-compose-prod.yml up -d --build
	@echo "✅ Services PROD démarrés"

docker-down-dev:
	docker compose -f docker-compose-dev.yml down --remove-orphans

docker-down-prod:
	docker compose -f docker-compose-prod.yml down --remove-orphans

docker-clean-dev:
	docker compose -f docker-compose-dev.yml down --remove-orphans --volumes
	@echo "✅ Services DEV arrêtés et volumes supprimés"

docker-clean-prod:
	docker compose -f docker-compose-prod.yml down --remove-orphans --volumes
	@echo "✅ Services PROD arrêtés et volumes supprimés"

# ──────────────────────────────────────────────
#  NETTOYAGE
# ──────────────────────────────────────────────
clean:
	find . -type d -name __pycache__ -exec rm -rf {} +
	find . -type f -name "*.pyc" -delete
	rm -rf .pytest_cache .coverage htmlcov .ruff_cache
	rm -rf dist build *.egg-info
	rm -f bootstrap_credentials.json
	@echo "✅ Fichiers temporaires supprimés"