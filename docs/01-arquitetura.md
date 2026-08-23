# 1. Arquitetura Completa Proposta

## 1.1 Princípios diretores

| # | Princípio | Consequência prática |
|---|-----------|----------------------|
| P1 | **Determinismo em Python, interpretação na IA** | Nenhum score, percentual, ranking ou data é calculado pelo LLM. `app/domain/scoring/*` é puro Python testável. |
| P2 | **Fatos vivem no banco** | Toda afirmação exibida ao usuário tem linha em tabela, com `source` e `confidence`. |
| P3 | **Proveniência obrigatória** | Todo dado extraído de edital carrega `page_number`, `char_start/end` e `evidence_level` (`OFFICIAL` / `INFERRED` / `NOT_FOUND`). |
| P4 | **Nada hardcoded de negócio** | Planos, limites, features e prompts são linhas de tabela + cache Redis, não constantes de código. |
| P5 | **HTTP nunca bloqueia** | Qualquer operação > 500 ms vai para Celery e reporta progresso por WebSocket/SSE. |
| P6 | **Provider-agnóstico** | O núcleo depende de `AIProvider` (porta), nunca de `openai`/`anthropic`/`google` diretamente. |
| P7 | **Explicabilidade** | Toda recomendação persiste seu vetor de contribuições (`score_breakdown` JSON) para renderizar o "POR QUÊ?". |
| P8 | **Conteúdo de PDF é hostil** | Texto de edital entra no prompt sempre dentro de envelope `<untrusted_document>` com instruções de não-obediência. |

## 1.2 Camadas

```
┌───────────────────────────────────────────────────────────────┐
│ CLIENTE — React 19 + TypeScript + Vite (SPA/PWA)              │
│ TanStack Query (server state) · Zustand (UI state)            │
└───────────────▲───────────────────────────────────────────────┘
                │ REST /api/v1 (JSON, OpenAPI 3.1) + WS /ws
┌───────────────┴───────────────────────────────────────────────┐
│ INTERFACE — FastAPI                                           │
│ routers · dependências · schemas Pydantic · middlewares       │
│ (request-id, CORS, security headers, rate limit, auth)        │
└───────────────▲───────────────────────────────────────────────┘
                │ DTOs
┌───────────────┴───────────────────────────────────────────────┐
│ APPLICATION SERVICES — casos de uso, orquestração, transações │
│ AuthService · UserService · NoticeAnalysisService ·           │
│ StudyPlanService · SimulationService · MestreChatService      │
└───────────────▲───────────────────────────────────────────────┘
                │ entidades + value objects
┌───────────────┴───────────────────────────────────────────────┐
│ DOMAIN — regras puras, sem I/O                                │
│ scoring (PriorityScore, MestreScore) · spaced repetition ·    │
│ planner · entitlements · policies · exceptions                │
└───────────────▲───────────────────────────────────────────────┘
                │ interfaces (Protocol/ABC)
┌───────────────┴───────────────────────────────────────────────┐
│ INFRASTRUCTURE — Repositories (SQLAlchemy 2 async) ·          │
│ Cache (Redis) · VectorStore (Qdrant) · Storage (S3/MinIO) ·   │
│ AIProvider · Mailer · PaymentGateway · YouTubeClient          │
└───────────────▲───────────────────────────────────────────────┘
                │
        MySQL 8 · Redis 7 · Qdrant · Object Storage · APIs externas
```

Regra de dependência: **as setas só apontam para dentro**. `domain` não importa `sqlalchemy`, `fastapi` nem SDK de LLM.

## 1.3 Divisão de processos

| Processo | Responsabilidade | Escala |
|---|---|---|
| `api` (uvicorn/gunicorn) | HTTP + WebSocket | horizontal, stateless |
| `worker-default` | e-mail, notificações, jobs curtos | horizontal |
| `worker-heavy` | PDF, OCR, embeddings, análise de edital | horizontal, CPU/IO alto |
| `worker-ai` | chamadas de LLM (fila isolada por causa de rate limit e custo) | concorrência baixa |
| `beat` | agendamentos (revisões, reta final, recomputo de scores) | singleton |
| `web` (nginx) | assets estáticos do SPA | CDN na frente |

Filas Celery: `default`, `documents`, `ai`, `analytics`, `notifications`. Cada fila com `rate_limit` e `time_limit` próprios.

## 1.4 Fluxo canônico — upload de edital

```
POST /notices/{id}/files (multipart)
  → valida MIME real (magic), tamanho, page count
  → grava em object storage com nome aleatório, bucket privado
  → cria notice_file (status=QUEUED) e retorna 202 + job_id
  → enfileira documents.process_notice_file

worker-heavy:
  extract(pdftext) → se cobertura textual < 60%, OCR
  → normaliza, chunk semântico, salva document_chunks (com page ref)
  → embeddings em lote → Qdrant (collection notices, payload notice_id)
  → publica progresso em Redis pubsub → WS /ws/jobs/{job_id}

worker-ai:
  extração estruturada por seção (structured output, schema Pydantic)
  → cada campo devolve {value, evidence: [{page, quote}], confidence}
  → validador Python confere que a quote existe literalmente no chunk;
    se não existir → evidence_level = INFERRED (nunca OFFICIAL)
  → persiste notice_sections/notice_events/subjects/topics
  → status=AWAITING_CONFIRMATION

Usuário confirma/corrige no Raio-X → gera study_plan (Python puro).
```

## 1.5 Segurança transversal

- Argon2id (parâmetros configuráveis por env) para senhas.
- JWT `access` (curto, 15 min) + `refresh` opaco/rotativo persistido (`user_sessions`), com detecção de reuso → revoga a família inteira.
- RBAC por permissão (`resource:action`), checada por dependência `require_permissions(...)`.
- Rate limit por IP + por usuário + por rota, sliding window em Redis.
- Auditoria imutável (`audit_logs`) para toda ação sensível.
- Upload: allowlist de MIME por conteúdo, limite de tamanho/páginas, quarentena, nome randômico, sem execução, servido só por URL assinada.
- Prompt injection: sanitização + envelope de documento não confiável + validação de saída estruturada.

## 1.6 Observabilidade

- `structlog` JSON com `request_id`, `user_id`, `route`, `latency_ms`.
- `/health` (liveness) e `/ready` (checa MySQL, Redis; Qdrant e storage quando habilitados).
- Métricas Prometheus em `/metrics` (opt-in por env): latência HTTP, filas, tokens de IA, custo por provider/modelo.
- OpenTelemetry opcional (`OTEL_EXPORTER_OTLP_ENDPOINT`), tracing API → worker via header de correlação.
