.PHONY: help dev up down build test lint migrate seed clean logs

COMPOSE := docker compose
COMPOSE_DEV := docker compose -f docker-compose.yml -f docker-compose.dev.yml

help: ## Show help
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | sort | awk 'BEGIN {FS = ":.*?## "}; {printf "\033[36m%-20s\033[0m %s\n", $$1, $$2}'

# ─── Development ───

dev: ## Start all services in dev mode
	$(COMPOSE_DEV) up --build

up: ## Start all services
	$(COMPOSE) up -d --build

down: ## Stop all services
	$(COMPOSE) down

build: ## Build all images
	$(COMPOSE) build

logs: ## Tail logs from all services
	$(COMPOSE) logs -f

logs-%: ## Tail logs from a specific service (e.g., make logs-api)
	$(COMPOSE) logs -f $*

restart-%: ## Restart a specific service
	$(COMPOSE) restart $*

# ─── Database ───

migrate: ## Run database migrations
	$(COMPOSE) exec api alembic -c /app/infra/migrations/alembic.ini upgrade head

migrate-gen: ## Generate a new migration (usage: make migrate-gen MSG="description")
	$(COMPOSE) exec api alembic -c /app/infra/migrations/alembic.ini revision --autogenerate -m "$(MSG)"

migrate-down: ## Rollback last migration
	$(COMPOSE) exec api alembic -c /app/infra/migrations/alembic.ini downgrade -1

seed: ## Seed database with initial data
	$(COMPOSE) exec api python /app/infra/scripts/seed.py

# ─── Testing ───

test: ## Run all tests
	$(COMPOSE) exec api pytest -xvs
	$(COMPOSE) exec graph-engine pytest -xvs
	$(COMPOSE) exec route-optimizer pytest -xvs
	$(COMPOSE) exec quality-oracle pytest -xvs
	$(COMPOSE) exec ingestion pytest -xvs

test-%: ## Run tests for specific service
	$(COMPOSE) exec $* pytest -xvs

# ─── Code Quality ───

lint: ## Run linter
	ruff check .
	ruff format --check .

fmt: ## Format code
	ruff check --fix .
	ruff format .

typecheck: ## Run type checker
	mypy packages/shared/meridian_shared
	mypy services/api/app
	mypy services/graph-engine/app
	mypy services/route-optimizer/app
	mypy services/quality-oracle/app
	mypy services/ingestion/app

# ─── Soroban ───

contract-build: ## Build Soroban contracts
	cd contracts/routing-registry && stellar contract build

contract-test: ## Test Soroban contracts
	cd contracts/routing-registry && cargo test

contract-deploy-testnet: ## Deploy contract to testnet
	cd contracts/routing-registry && stellar contract deploy \
		--wasm target/wasm32-unknown-unknown/release/routing_registry.wasm \
		--network testnet

# ─── Cleanup ───

clean: ## Remove all containers, volumes, and images
	$(COMPOSE) down -v --rmi local
	find . -type d -name __pycache__ -exec rm -rf {} + 2>/dev/null || true
	find . -type d -name .pytest_cache -exec rm -rf {} + 2>/dev/null || true
	find . -type f -name "*.pyc" -delete 2>/dev/null || true

# ─── Health ───

health: ## Check health of all services
	@echo "API:              $$(curl -sf http://localhost:8000/health | jq -r .status)"
	@echo "Graph Engine:     $$(curl -sf http://localhost:8001/health | jq -r .status)"
	@echo "Route Optimizer:  $$(curl -sf http://localhost:8002/health | jq -r .status)"
	@echo "Quality Oracle:   $$(curl -sf http://localhost:8003/health | jq -r .status)"
	@echo "Predictive Engine:$$(curl -sf http://localhost:8004/health | jq -r .status)"
	@echo "Ingestion:        $$(curl -sf http://localhost:8005/health | jq -r .status)"
