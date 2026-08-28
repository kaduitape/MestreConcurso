# 2. Estrutura de Diretórios

Legenda: **(F1)** entregue na Fase 1 · *(itálico)* previsto para fases seguintes.

## 2.1 Raiz

```
MestreConcurso/
├── docker-compose.yml            (F1)
├── docker-compose.override.yml   (F1)  # hot reload de dev
├── .env.example                  (F1)
├── Makefile                      (F1)
├── README.md                     (F1)
├── docs/                         (F1)
├── backend/                      (F1)
└── frontend/                     (F1)
```

## 2.2 Backend

```
backend/
├── Dockerfile                    (F1)
├── pyproject.toml                (F1)
├── alembic.ini                   (F1)
├── alembic/versions/             (F1)
├── app/
│   ├── main.py                   (F1)  # cria app, monta middlewares e routers
│   ├── core/
│   │   ├── config.py             (F1)  # Settings (pydantic-settings)
│   │   ├── security.py           (F1)  # Argon2, JWT, tokens opacos
│   │   ├── logging.py            (F1)  # structlog
│   │   ├── errors.py             (F1)  # AppError → handler HTTP padronizado
│   │   ├── pagination.py         (F1)
│   │   ├── rate_limit.py         (F1)  # sliding window Redis
│   │   ├── redis.py              (F1)
│   │   └── middleware.py         (F1)  # request-id, security headers, timing
│   ├── db/
│   │   ├── base.py               (F1)  # DeclarativeBase + mixins
│   │   ├── session.py            (F1)  # engine + async_sessionmaker
│   │   └── types.py              (F1)  # tipos portáveis (UUID, JSON, TEXT)
│   ├── models/                   (F1 parcial)
│   │   ├── user.py, role.py, session.py, token.py,
│   │   ├── audit.py, consent.py  (F1)
│   │   └── competition.py, notice.py, subject.py, question.py,
│   │       study.py, flashcard.py, simulation.py, ai.py, billing.py
│   ├── schemas/                  (F1 parcial)
│   ├── repositories/             (F1 parcial)
│   │   ├── base.py               (F1)  # CRUD genérico tipado
│   │   └── user.py, role.py, session.py, audit.py (F1)
│   ├── services/                 (F1 parcial)
│   │   ├── auth.py, user.py, admin.py, audit.py, email.py (F1)
│   │   └── notice_analysis.py, planner.py, simulation.py, chat.py
│   ├── domain/                   # Python puro: sem I/O, sem IA, sem SQLAlchemy
│   │   ├── permissions.py        (F1)  # catálogo de permissões
│   │   ├── entitlements.py       (F1)  # avaliador de feature flags
│   │   ├── evidence.py           (F3)  # conferência literal de citação
│   │   ├── ai_features.py        (F2)  # catálogo de funcionalidades de IA
│   │   ├── trap_catalogue.py     (F6)  # padrões de pegadinha (editorial)
│   │   ├── planner/              (F4)  # alocação, agenda, sprint, replanejamento
│   │   ├── questions/            (F5)  # correção e seleção de questões
│   │   ├── intelligence/         (F6)  # incidência, Priority Score, perfil, erros
│   │   ├── tutor/                (F7)  # preparo da pergunta, fusão, conferência
│   │   ├── srs/                  (F8)  # intervalos e fila de revisão
│   │   └── game/                 (G1)  # XP, níveis, ranks, streak, missões
│   ├── api/
│   │   ├── deps.py               (F1)  # get_db, current_user, require_perm
│   │   └── v1/
│   │       ├── router.py         (F1)
│   │       └── routers/{auth,users,admin,health}.py (F1)
│   ├── ai/                       (F3+)
│   │   ├── base.py               # AIProvider (porta)
│   │   ├── providers/{openai,gemini,anthropic}.py
│   │   ├── engine.py             # orquestrador RAG
│   │   ├── prompts/              # prompts versionados (arquivo + tabela)
│   │   ├── chunking.py, rerank.py, vector_store.py, budget.py
│   └── workers/
│       ├── celery_app.py         (F1)
│       └── tasks/{email,maintenance}.py (F1)
└── tests/
    ├── conftest.py               (F1)
    ├── unit/                     (F1)
    └── integration/              (F1)
```

## 2.3 Frontend

```
frontend/
├── Dockerfile / nginx.conf       (F1)
├── vite.config.ts, tsconfig*.json, tailwind.config.ts (F1)
└── src/
    ├── main.tsx, App.tsx, routes.tsx           (F1)
    ├── styles/globals.css                      (F1)  # tokens do design system
    ├── lib/
    │   ├── api/client.ts                       (F1)  # fetch + refresh automático
    │   ├── api/{auth,users,admin}.ts           (F1)
    │   ├── query-client.ts, utils.ts           (F1)
    ├── components/
    │   ├── ui/                                 (F1)  # botão, input, card, dialog,
    │   │                                              sheet, table, toast, skeleton…
    │   ├── layout/{AppShell,Sidebar,Topbar}    (F1)
    │   ├── command/CommandPalette.tsx          (F1)  # Ctrl+K
    │   └── feedback/{EmptyState,ErrorState}    (F1)
    ├── features/
    │   ├── auth/                               (F1)
    │   ├── account/                            (F1)  # perfil, senha, dispositivos
    │   ├── admin/                              (F1)
    │   ├── today/                              (F1 shell)
    │   └── notices/, planner/, questions/, simulations/, mestre-ia/
    ├── hooks/, providers/{Theme,Auth}          (F1)
    └── types/api.ts                            (F1)
```
