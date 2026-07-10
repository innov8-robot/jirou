# ============================================================
# Jirou — raccourcis dev & tests
# ============================================================
.DEFAULT_GOAL := help
COMPOSE := docker compose

.PHONY: help up down build rebuild logs ps \
        test test-backend test-frontend test-e2e e2e-up

help: ## Affiche cette aide
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | \
		awk 'BEGIN{FS=":.*?## "}{printf "  \033[36m%-16s\033[0m %s\n", $$1, $$2}'

## ---- Stack ----
up: ## Démarre la stack (build si besoin)
	@[ -f .env ] || cp .env.example .env
	$(COMPOSE) up -d --build

down: ## Arrête la stack
	$(COMPOSE) down

build: ## Construit les images
	$(COMPOSE) build

rebuild: ## Reconstruit sans cache
	$(COMPOSE) build --no-cache

fe-deps: ## À lancer après ajout d'une dépendance npm : rebuild image + renouvelle le node_modules du conteneur
	$(COMPOSE) build frontend
	$(COMPOSE) up -d --force-recreate --renew-anon-volumes frontend

logs: ## Suit les logs
	$(COMPOSE) logs -f

ps: ## État des conteneurs
	$(COMPOSE) ps

## ---- Tests ----
test: test-backend test-frontend test-e2e ## Lance TOUTE la suite de tests

test-backend: ## Tests backend (pytest) sur un Postgres jetable isolé
	@bash scripts/test-backend.sh

test-frontend: ## Tests frontend (vitest)
	cd frontend && npm run test

test-e2e: ## Tests end-to-end contre la stack en marche (la démarre si besoin)
	@bash scripts/e2e.sh
