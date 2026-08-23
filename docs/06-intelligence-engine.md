# 6. Arquitetura do Concurso Intelligence Engine

Camada isolada em `backend/app/ai/`, sem dependência de FastAPI. Consumida por services via interface.

## 6.1 Portas e adaptadores

```
                       ┌─────────────────────────────┐
   services ──────────▶│  IntelligenceEngine         │
                       │  (fachada única)            │
                       └───┬───────┬────────┬────────┘
                           │       │        │
              ┌────────────▼──┐ ┌──▼──────┐ ┌▼─────────────┐
              │ Retrieval     │ │ Prompt  │ │ Budget/Cost  │
              │ (VectorStore, │ │ Registry│ │ Guard        │
              │  Reranker)    │ │ (versão)│ └──────────────┘
              └───────────────┘ └─────────┘
                           │
                    ┌──────▼───────┐
                    │  AIProvider  │  (porta)
                    └──┬────┬───┬──┘
        OpenAIProvider ─┘    │   └─ AnthropicProvider
                     GeminiProvider  … FutureProvider
```

### Contrato `AIProvider`

```python
class AIProvider(Protocol):
    name: str
    async def complete(self, req: CompletionRequest) -> CompletionResult: ...
    async def stream(self, req: CompletionRequest) -> AsyncIterator[StreamChunk]: ...
    async def structured(self, req: StructuredRequest[T]) -> StructuredResult[T]: ...
    async def embed(self, texts: list[str], model: str) -> EmbeddingResult: ...
    async def rerank(self, query: str, docs: list[str], model: str) -> list[Ranked]: ...
    def count_tokens(self, text: str, model: str) -> int: ...
    def capabilities(self, model: str) -> ModelCapabilities: ...
```

`CompletionRequest` é neutro (mensagens, tools, `response_schema`, `temperature`, `max_tokens`, `metadata`). Cada adaptador traduz para o SDK do fornecedor e normaliza a resposta (inclusive `usage` e erros → taxonomia comum: `RateLimited`, `ContextOverflow`, `ProviderUnavailable`, `SafetyBlocked`, `InvalidSchema`).

## 6.2 Seleção de modelo em runtime

`ai_providers` / `ai_models` / `feature_model_bindings` no banco. O admin escolhe, por *feature* (`notice.extraction`, `chat.tutor`, `question.classify`, `embeddings.default`, `rerank.default`), qual modelo usar, com fallback ordenado. Cache em Redis (TTL 60 s) + invalidação por evento. Nenhuma referência a nome de modelo no código de negócio.

## 6.3 Prompts versionados

- Arquivo `app/ai/prompts/<slug>/v<N>.md` (fonte de verdade em code review) sincronizado para a tabela `ai_prompts` na inicialização.
- Toda chamada registra `prompt_slug` + `version` em `ai_usage`/`ai_messages` → resposta sempre reproduzível.
- Suporte a A/B por percentual de tráfego (feature flag).

## 6.4 Controle de tokens e custo

```
antes:  estimate_tokens(prompt) → checa entitlement (usage_limits) e orçamento global
        → se estourar: erro 402/429 com mensagem clara, sem chamar o provider
depois: registra input/output/cached tokens, custo (tabela de preço por modelo),
        latência e status em ai_usage → dashboards de MRR/custo e alertas
```

Circuit breaker por provider (N falhas em janela → fallback), retry exponencial com jitter apenas para erros transitórios, timeout duro por feature.

## 6.5 Cache

| Nível | Chave | TTL |
|---|---|---|
| Recuperação | hash(query + filtros + versão do índice) | 6 h |
| Structured output determinístico (temp=0) | hash(prompt + schema + modelo) | 24 h |
| Prompt caching nativo do provider | prefixo de sistema/documento | conforme provider |
| Conteúdo didático gerado | `topic_id + nível + versão do prompt` | até invalidação |

## 6.6 Streaming e histórico

- SSE para chat (`text/event-stream`) e WebSocket para progresso de jobs.
- Eventos tipados: `token`, `tool_call`, `citation`, `usage`, `done`, `error`.
- Histórico: janela recente completa + resumo incremental das mensagens antigas (gerado por job), sempre acompanhado do "contexto do aluno" montado por Python (edital, banca, últimos erros, próximas revisões) — nunca reconstruído pelo LLM.

## 6.7 Function calling

Ferramentas expostas ao tutor, todas com execução em Python e permissão checada:
`get_edital_section`, `get_topic_incidence`, `get_user_weak_points`, `get_due_reviews`,
`generate_flashcards`, `create_practice_set`, `schedule_review`, `explain_error`.
O LLM **propõe**; o service executa, valida e persiste. Toda ferramenta que escreve exige confirmação explícita do usuário na UI.

## 6.8 Divisão inegociável

| Python | IA |
|---|---|
| percentuais, médias, incidência, Priority Score, Mestre Score, projeções, datas, rankings, orçamento | interpretação de texto, classificação, explicação didática, geração de questões/flashcards, personalização de linguagem, sugestão de prioridade textual |
