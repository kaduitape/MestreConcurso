# 3. Diagrama de Serviços

## 3.1 Topologia

```
                        ┌──────────────┐
        Browser ───────▶│  web (nginx) │  SPA estático + gzip/brotli + cache
                        └──────┬───────┘
                               │ /api, /ws  (proxy)
                        ┌──────▼───────┐
                        │  api         │  FastAPI (uvicorn workers)
                        └──┬───┬───┬───┘
             ┌─────────────┘   │   └────────────────┐
             │                 │                    │
      ┌──────▼─────┐   ┌───────▼──────┐     ┌───────▼───────┐
      │ MySQL 8    │   │ Redis 7      │     │ Qdrant        │
      │ dados      │   │ cache, rate  │     │ vetores       │
      │ transac.   │   │ limit, lock, │     │ (F3+)         │
      └──────▲─────┘   │ broker, ps   │     └───────▲───────┘
             │         └───┬─────┬────┘             │
             │             │     │                  │
      ┌──────┴─────────────▼─┐ ┌─▼──────────────────┴────┐
      │ worker-default       │ │ worker-heavy / worker-ai│
      │ e-mail, notificações │ │ PDF, OCR, embeddings,   │
      └──────────────────────┘ │ LLM, analytics          │
                  ▲            └───────┬─────────────────┘
                  │                    │
            ┌─────┴──────┐      ┌──────▼──────────────────────────┐
            │ beat       │      │ Externos: LLM APIs · YouTube    │
            │ (cron)     │      │ Mercado Pago · SMTP · S3/MinIO  │
            └────────────┘      └─────────────────────────────────┘
```

## 3.2 Contratos entre serviços

| Origem | Destino | Protocolo | Observação |
|---|---|---|---|
| SPA | api | HTTPS REST | `Authorization: Bearer <access>`; refresh em cookie `HttpOnly` opcional |
| SPA | api | WebSocket `/ws/jobs/{job_id}` | progresso de jobs; autenticado por ticket de curta duração |
| api | Redis | RESP | cache, rate limit, locks, pub/sub, broker Celery |
| api | Celery | broker Redis | `apply_async` com `queue` explícita |
| worker | Redis pub/sub | RESP | publica eventos de progresso consumidos pelo WS |
| worker-ai | LLM | HTTPS | timeout, retry exponencial, circuit breaker, orçamento de tokens |
| api/worker | S3/MinIO | HTTPS | URLs assinadas, bucket privado |
| Mercado Pago | api | Webhook HTTPS | assinatura verificada, idempotência por `event_id` |

## 3.3 Jobs agendados (beat)

| Job | Cadência | Fila |
|---|---|---|
| `recompute_priority_scores` | 04:00 diário + on-demand | analytics |
| `build_daily_missions` | 03:30 diário | analytics |
| `spaced_repetition_rollover` | 00:10 diário | default |
| `check_exam_proximity_modes` | diário | default |
| `sync_notice_events` | horário | default |
| `ai_cost_rollup` | horário | analytics |
| `purge_expired_tokens_sessions` | horário | default |
| `lgpd_retention_sweep` | diário | default |
