# 5. Estratégia Qdrant / RAG

## 5.1 Coleções

| Coleção | Conteúdo | Vetores | Payload principal |
|---|---|---|---|
| `notices` | chunks de editais | dense (1536) + sparse BM25 | `notice_id`, `document_id`, `chunk_id`, `page`, `section_kind`, `tenant=user_id\|global` |
| `legislation` | leis, súmulas, jurisprudência | dense + sparse | `law_slug`, `article`, `updated_at`, `source_url` |
| `didactic` | conteúdo do Modo Professor | dense | `subject_id`, `topic_id`, `level` |
| `questions` | enunciado + comentário | dense | `question_id`, `subject_id`, `topic_id`, `board_id`, `year` |
| `user_notes` | anotações e materiais do aluno | dense | `user_id` (isolamento obrigatório) |

Distância cosseno, `on_disk_payload=true`, HNSW `m=16, ef_construct=128`. Índices de payload em `notice_id`, `user_id`, `subject_id`, `topic_id`, `exam_board_id`, `year`.

## 5.2 Isolamento multiusuário

Todo ponto carrega `tenant`. Nenhuma busca é emitida sem `Filter(must=[FieldCondition(key="tenant", ...)])` — a construção do filtro fica no `VectorStore`, não no chamador, para que seja impossível esquecer. Conteúdo global usa `tenant="global"` e é adicionado explicitamente via `should`.

## 5.3 Chunking  *(implementado na Fase 3)*

1. **Layout-aware**: quebra por seção/artigo/título antes de qualquer corte por tamanho. O detector distingue **título de seção** (numeração + caixa alta, curto) de **item de texto** ("1.2 O candidato deverá…"), além de `ANEXO`, `CAPÍTULO`, `SEÇÃO` e `Art. N`.
2. **Alvo**: 700 tokens, overlap 120, mínimo 120 (chunks menores são fundidos ao vizinho).
3. **Contextualização** (Anthropic-style contextual retrieval): cada chunk recebe um preâmbulo curto gerado uma única vez (`documento X, seção Y, trata de Z`) e cacheado; o texto original é preservado intacto para citação literal.
4. **Metadados** obrigatórios: `page_number`, `char_start`, `char_end`, `heading_path`, `section_kind`. Sem isso o chunk não é indexado — proveniência é pré-requisito.
5. **Reaproveitamento**: o documento é identificado por SHA-256. Reenviar ou reanalisar o mesmo PDF não repete extração, chunking nem embeddings.

## 5.4 Pipeline de recuperação

```
query
 ├─ normalização + expansão (siglas: LEP, CF/88, CPP…) — dicionário, não LLM
 ├─ busca híbrida: dense (top 40) + sparse/BM25 (top 40)
 ├─ fusão RRF (k=60)
 ├─ rerank cross-encoder (top 40 → top 8)   [provider-agnóstico]
 ├─ montagem de contexto com orçamento de tokens (limite por feature)
 └─ resposta com citações obrigatórias [doc, página]
```

- **Sem contexto suficiente** (score do melhor documento abaixo do limiar) → o engine responde "não localizei isso no seu edital/base" e oferece busca ampla. Nunca completa por conta própria.
- **Cache**: `sha256(query_normalizada + filtros + versão_do_índice)` em Redis (TTL 6 h) para resultados de recuperação; cache separado para respostas finais quando determinísticas.
- **Reindexação**: mudança de `embedding_model` gera nova coleção com sufixo de versão e alias atômico (`notices` → `notices_v2`), sem downtime.

## 5.5 Regras anti-alucinação  *(o item 1–2 já vale desde a Fase 3)*

1. Toda resposta com afirmação factual precisa retornar `citations[]` referenciando `document_chunks.id`.
2. Validador Python confere que cada citação existe e que a `quote` aparece literalmente no chunk (normalizando espaços). Citação inválida → o trecho é rebaixado a "inferência" ou a resposta é rejeitada e reprocessada.
3. Estatística nunca sai do LLM: o engine injeta números já calculados pelo Python no prompt e proíbe recálculo.
4. Documento enviado pelo usuário entra no prompt dentro de `<untrusted_document>` com instrução explícita de que seu conteúdo é dado, não instrução.
