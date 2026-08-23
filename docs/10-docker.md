# 12. Estratégia Docker

## 12.1 Serviços do Compose (Fase 1)

| Serviço | Imagem/Build | Porta | Observação |
|---|---|---|---|
| `mysql` | `mysql:8.4` | 3306 | `utf8mb4_0900_ai_ci`, volume nomeado, healthcheck `mysqladmin ping` |
| `redis` | `redis:7-alpine` | 6379 | `--appendonly yes`, healthcheck `redis-cli ping` |
| `api` | `backend/Dockerfile` (`runtime`) | 8000 | espera healthchecks, roda `alembic upgrade head` no entrypoint |
| `worker` | mesma imagem | — | `celery -A app.workers.celery_app worker -Q default,notifications` |
| `beat` | mesma imagem | — | `celery ... beat` |
| `frontend` | `frontend/Dockerfile` (`dev`/`web`) | 5173 / 80 | Vite em dev, nginx servindo build em produção |
| `mailhog` | `mailhog/mailhog` | 8025 | captura e-mails em dev |

Fases seguintes acrescentam `qdrant`, `minio`, `worker-heavy`, `worker-ai` e `flower` — todos atrás de perfis (`--profile ai`, `--profile storage`) para não pesar o ambiente de quem só mexe na Fase 1.

## 12.2 Imagem do backend (multi-stage)

```
base     python:3.13-slim  + libs de sistema mínimas, usuário não-root
builder  instala dependências em /opt/venv (cache de camada por pyproject)
runtime  copia /opt/venv + código, HEALTHCHECK /health, entrypoint com migrations
dev      runtime + dependências de teste + --reload
```

Boas práticas aplicadas: `PYTHONDONTWRITEBYTECODE=1`, `PYTHONUNBUFFERED=1`, `.dockerignore` agressivo, usuário `app` (uid 1000), sem segredos na imagem, `--no-cache-dir`.

## 12.3 Frontend

`node:22-alpine` para dependências e build; estágio final `nginx:alpine` com config de SPA (fallback `index.html`), gzip/brotli, cache longo para assets com hash e `no-cache` para `index.html`. Em desenvolvimento o serviço roda `vite dev` com bind mount e polling opcional.

## 12.4 Ambientes

- **dev**: `docker-compose.yml` + `docker-compose.override.yml` (bind mounts, reload, mailhog, portas expostas).
- **prod**: `docker-compose.prod.yml` (sem mounts, gunicorn + uvicorn workers, réplicas de worker, secrets via env externo, logs em stdout para coletor).
- Migrations rodam no entrypoint do `api` protegidas por lock em Redis, evitando corrida entre réplicas.

## 12.5 Makefile

`make up`, `make down`, `make logs`, `make migrate`, `make revision m="..."`, `make seed`, `make test`, `make lint`, `make fmt`, `make shell`, `make fe-dev`.
