# 11. Dependências e Bibliotecas Recomendadas

## 11.1 Backend (Python 3.13)

| Área | Pacote | Motivo |
|---|---|---|
| Web | `fastapi`, `uvicorn[standard]`, `gunicorn` | ASGI + OpenAPI 3.1 |
| Dados | `sqlalchemy[asyncio]>=2.0`, `alembic`, `asyncmy` | ORM 2.0 tipado + driver MySQL async |
| Validação | `pydantic>=2`, `pydantic-settings`, `email-validator` | schemas e config tipada |
| Segurança | `argon2-cffi`, `pyjwt[crypto]`, `itsdangerous` | Argon2id, JWT, assinaturas |
| Cache/fila | `redis>=5`, `celery[redis]`, `flower` | cache, rate limit, broker, monitor |
| Observabilidade | `structlog`, `prometheus-client`, `opentelemetry-*` | logs JSON, métricas, tracing |
| Arquivos | `python-multipart`, `boto3`, `python-magic` | upload, S3/MinIO, MIME real |
| PDF/OCR (F3) | `pymupdf`, `pdfplumber`, `ocrmypdf`/`pytesseract` | extração + OCR condicional |
| Vetores (F3) | `qdrant-client`, `tiktoken`, `rank-bm25` | busca híbrida |
| IA (F3+) | `httpx` + SDKs oficiais isolados nos adaptadores | sem acoplamento no core |
| E-mail | `fastapi-mail`/`aiosmtplib`, `jinja2` | templates transacionais |
| Pagamentos (F10) | `mercadopago` | gateway |
| Testes | `pytest`, `pytest-asyncio`, `httpx`, `aiosqlite`, `factory-boy`, `freezegun`, `coverage` | unit + integração |
| Qualidade | `ruff`, `mypy`, `pre-commit` | lint, format, tipos |

## 11.2 Frontend

| Área | Pacote |
|---|---|
| Base | `react`, `react-dom`, `typescript`, `vite`, `react-router-dom` |
| Estilo | `tailwindcss`, `tailwind-merge`, `clsx`, `class-variance-authority`, `tailwindcss-animate` |
| UI | primitivos Radix/Base UI (`@radix-ui/react-*`) no padrão shadcn/ui, `lucide-react`, `sonner`, `cmdk` |
| Dados | `@tanstack/react-query`, `@tanstack/react-table`, `@tanstack/react-virtual` |
| Formulários | `react-hook-form`, `zod`, `@hookform/resolvers` |
| Gráficos | `recharts` (a partir da Fase 6, com dados reais) |
| Animação | `framer-motion` |
| Datas | `date-fns` |
| Qualidade | `eslint`, `prettier`, `vitest`, `@testing-library/react`, `playwright` (E2E, F4+) |
| PWA | `vite-plugin-pwa` (F41) |

## 11.3 Infra

`mysql:8.4`, `redis:7-alpine`, `qdrant/qdrant` (F3), `minio` (F3), `mailhog` (dev), `nginx:alpine` (build de produção do SPA).
