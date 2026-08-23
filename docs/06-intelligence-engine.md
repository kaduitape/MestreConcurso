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

## 6.2 Seleção de modelo em runtime  *(implementado na Fase 2)*

`ai_providers` / `ai_models` / `ai_feature_bindings` no banco. O admin escolhe, por *feature* (`notice.extraction`, `board.profile`, `chat.tutor`, `question.classify`, `flashcard.generation`, `embeddings.default`, `rerank.default`), qual modelo usar. Nenhuma referência a nome de modelo no código de negócio.

Fluxo do painel (`/admin` → aba **Inteligência**):

```
Conectar provedor (openai)      → linha em ai_providers, inativo
Informar a chave                 → cifrada (Fernet + HKDF sobre SECRET_KEY)
                                   guardamos só o texto cifrado + dica "sk-…7890"
Testar conexão                   → GET /v1/models real; grava status, latência e amostra
Importar modelos                 → popula ai_models com o que a chave realmente acessa
Ativar provedor                   → só é permitido depois que existe chave
Escolher modelo por funcionalidade → ai_feature_bindings (com TTL de cache por feature)
```

Regras de segurança: a chave nunca volta pela API (nem em log, nem em auditoria — só a dica); trocar o `SECRET_KEY` invalida os segredos gravados e exige recadastro; toda ação fica em `audit_logs`.

`AISettingsService.resolve_feature(feature)` devolve provedor + modelo prontos, ou levanta `ProviderNotConfiguredError` — a plataforma avisa em vez de fingir que respondeu.

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

## 6.5 Cache e reaproveitamento  *(implementado na Fase 2)*

Princípio: **nada que já foi apurado é pago duas vezes.** Duas camadas persistentes, ambas em MySQL (sobrevivem a restart, deploy e limpeza de Redis):

**1. `ai_cache_entries` — cache de resposta por impressão digital**

```
fingerprint = sha256(feature | model_slug | prompt_version | json_canônico(entrada))
```

`AICacheService.get()` devolve a resposta gravada e incrementa `hits`; `store()` grava resposta, tokens e custo. `stats()` reporta, a partir dos contadores reais: entradas, reaproveitamentos, **tokens economizados** (`hits × tokens`) e custo evitado. Mudou o modelo ou a versão do prompt → a impressão digital muda → resposta nova, sem servir conteúdo desatualizado.

**2. `board_knowledge_entries` — o que se sabe de cada banca**

Todo traço de estilo, padrão de pegadinha, foco por disciplina ou resumo de perfil é gravado com `source` (`COMPUTED` / `AI` / `EDITORIAL` / `OFFICIAL`), `confidence`, tamanho de amostra (`sample_exams`, `sample_questions`), período analisado, modelo e versão do prompt usados, tokens consumidos e validade (`expires_at`). As telas leem desta tabela; a IA só é acionada quando `get_valid()` não encontra registro. Registro vencido continua visível ao administrador (marcado como vencido, para reapurar) e some para o candidato.

| Nível | Chave | TTL |
|---|---|---|
| Resposta de IA (implementado) | `sha256(feature+modelo+versão do prompt+entrada)` | por feature, definido no painel |
| Conhecimento de banca (implementado) | `banca + tipo + chave` | `ttl_days` por registro; vazio = permanente |
| Recuperação (F3) | hash(query + filtros + versão do índice) | 6 h |
| Prompt caching nativo do provider (F3) | prefixo de sistema/documento | conforme provider |

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
