# =============================================================================
# ConversalQ — Makefile for common development commands
# =============================================================================

.PHONY: help dev up down build test lint format migrate

help: ## Show this help
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | sort | awk 'BEGIN {FS = ":.*?## "}; {printf "\033[36m%-20s\033[0m %s\n", $$1, $$2}'

# --- Docker ---
dev: ## Start development environment
	docker compose -f infra/docker-compose.yml -f infra/docker-compose.dev.yml up --build

up: ## Start production environment
	docker compose -f infra/docker-compose.yml up --build -d

down: ## Stop all services
	docker compose -f infra/docker-compose.yml down

build: ## Build Docker images
	docker compose -f infra/docker-compose.yml build

logs: ## Tail logs
	docker compose -f infra/docker-compose.yml logs -f backend

# --- Local Development ---
install: ## Install dependencies locally
	cd backend && pip install -r requirements-dev.txt

run: ## Run backend locally
	cd backend && uvicorn app.main:app --reload --host 0.0.0.0 --port 8000

# --- Testing ---
test: ## Run tests
	cd backend && pytest tests/ -v --cov=app --cov-report=term-missing

test-unit: ## Run unit tests only
	cd backend && pytest tests/unit/ -v

# --- Code Quality ---
lint: ## Run linter
	cd backend && ruff check app/ tests/

format: ## Format code
	cd backend && ruff format app/ tests/

typecheck: ## Run type checker
	cd backend && mypy app/

# --- Database ---
migrate: ## Run database migrations
	cd backend && alembic upgrade head

migrate-create: ## Create a new migration (usage: make migrate-create msg="add users table")
	cd backend && alembic revision --autogenerate -m "$(msg)"
