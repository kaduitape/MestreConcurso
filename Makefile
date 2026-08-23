COMPOSE ?= docker compose
BACKEND ?= $(COMPOSE) exec api

.DEFAULT_GOAL := help

.PHONY: help
help: ## Lista os comandos disponíveis
	@grep -hE '^[a-zA-Z_-]+:.*?## ' $(MAKEFILE_LIST) \
	 | awk 'BEGIN {FS = ":.*?## "}; {printf "  \033[36m%-16s\033[0m %s\n", $$1, $$2}'

.PHONY: setup
setup: ## Cria o .env a partir do exemplo (não sobrescreve)
	@test -f .env || (cp .env.example .env && echo ".env criado — revise os segredos antes de subir.")

.PHONY: up
up: setup ## Sobe toda a stack
	$(COMPOSE) up -d --build

.PHONY: down
down: ## Derruba a stack (mantém volumes)
	$(COMPOSE) down

.PHONY: reset
reset: ## Derruba a stack e apaga os volumes (perde os dados)
	$(COMPOSE) down -v

.PHONY: logs
logs: ## Acompanha os logs da API e dos workers
	$(COMPOSE) logs -f api worker beat

.PHONY: ps
ps: ## Estado dos serviços
	$(COMPOSE) ps

.PHONY: migrate
migrate: ## Aplica as migrations
	$(BACKEND) alembic upgrade head

.PHONY: downgrade
downgrade: ## Reverte a última migration
	$(BACKEND) alembic downgrade -1

.PHONY: revision
revision: ## Gera migration (uso: make revision m="mensagem")
	$(BACKEND) alembic revision --autogenerate -m "$(m)"

.PHONY: seed
seed: ## Sincroniza papéis/permissões e garante o admin inicial
	$(BACKEND) python -m app.cli seed

.PHONY: test
test: ## Testes do backend
	$(BACKEND) pytest -q

.PHONY: lint
lint: ## Lint e tipagem do backend
	$(BACKEND) ruff check app tests
	$(BACKEND) mypy app

.PHONY: fmt
fmt: ## Formata o backend
	$(BACKEND) ruff format app tests
	$(BACKEND) ruff check --fix app tests

.PHONY: shell
shell: ## Shell dentro do container da API
	$(BACKEND) bash

.PHONY: fe-dev
fe-dev: ## Frontend em modo desenvolvimento (fora do Docker)
	cd frontend && npm run dev

.PHONY: fe-test
fe-test: ## Testes do frontend
	cd frontend && npm run test -- --run

.PHONY: fe-lint
fe-lint: ## Lint e checagem de tipos do frontend
	cd frontend && npm run lint && npm run typecheck
