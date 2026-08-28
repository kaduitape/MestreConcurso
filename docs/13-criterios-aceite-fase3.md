# Critérios de Aceite — Fase 3 (Análise de Edital com IA)

## Extração do PDF
1. `POST /admin/notices/{id}/analyze` extrai o texto página a página com PyMuPDF, preservando a numeração real das páginas (a primeira é 1).
2. Hifenização de fim de linha é reunida (`adminis-\ntração` → `administração`) e espaços redundantes colapsados, sem destruir a quebra de blocos.
3. PDF sem camada de texto é detectado por cobertura (< 60% das páginas com texto aproveitável) e vai para OCR quando o Tesseract está disponível na imagem.
4. Sem OCR disponível, a análise **falha com mensagem acionável** (`ocr_required`) em vez de seguir com texto vazio.
5. PDF corrompido (`unreadable_pdf`), protegido por senha (`encrypted_pdf`) e acima do limite de páginas (`pdf_too_long`) são recusados com código próprio.

## Estruturação em trechos
6. A quebra respeita a estrutura do edital: títulos de seção (numeração + caixa alta), `ANEXO`, `CAPÍTULO`, `SEÇÃO` e `Art. N` cortam o trecho antes do limite de tamanho.
7. Item numerado comum ("1.2 O candidato deverá…") **não** é confundido com título de seção.
8. Todo trecho guarda `page_number`, `char_start`, `char_end`, `heading_path` e `section_kind` — sem isso não existe prova de origem.
9. A seção é classificada automaticamente (disciplinas, cronograma, inscrições, provas, eliminação, TAF, recursos).

## Indexação vetorial
10. Com modelo de embeddings configurado, os trechos são vetorizados e gravados no Qdrant com `tenant`, `document_id`, `chunk_id` e página no payload.
11. O filtro de `tenant` é montado dentro do `VectorStore`: material de um aluno nunca aparece na busca de outro, e conteúdo `global` é visível a todos.
12. Sem modelo de embeddings configurado, a etapa é **pulada com motivo explícito** — a análise continua, a busca semântica é que fica indisponível.

## Extração com IA e prova de origem
13. O prompt é versionado em arquivo (`app/ai/prompts/notice_extraction/v1.md`) e a versão usada fica gravada em cada campo.
14. O conteúdo do edital vai ao modelo dentro de `<untrusted_document>`, com instrução explícita de ignorar ordens que apareçam no documento (defesa contra prompt injection).
15. **Regra central:** cada campo só é `OFICIAL` quando a citação devolvida pelo modelo é encontrada literalmente no PDF (comparação sem acento, sem caixa e com espaços normalizados).
16. Citação inventada rebaixa o campo a `INFERIDO` — e, sem citação conferida, **a página não é exibida**: página informada pelo modelo, sem prova, seria falsa origem.
17. Citação com menos de 12 caracteres nunca vale como prova (casaria por acaso).
18. Campo ausente no edital vira `NÃO LOCALIZADO`, com valor nulo — nada é deduzido.
19. Evento de cronograma sem data legível é descartado em vez de virar data inventada.
20. Resposta fora do formato esperado é rejeitada (`invalid_ai_response`), sem gravar nada pela metade.
21. Sem funcionalidade `notice.extraction` configurada, a análise responde `409 ai_provider_not_configured` apontando o painel — a plataforma avisa em vez de adivinhar.

## Reaproveitamento (custo)
22. O mesmo PDF (SHA-256 igual) não é extraído nem dividido novamente: o documento é reusado e as etapas aparecem como puladas.
23. A mesma combinação (documento + modelo + versão do prompt) não gera nova chamada ao provedor: a resposta vem do cache e o painel contabiliza os tokens economizados.
24. Trocar o modelo ou a versão do prompt muda a impressão digital e provoca nova extração — cache não serve resposta desatualizada.

## Acompanhamento, revisão e Raio-X
25. O progresso é persistido no banco em sete etapas nomeadas e transmitido por SSE (`/analysis/stream`); recarregar a página no meio do processamento não perde o estado.
26. A interface mostra o checklist com o resultado de cada etapa — nunca um spinner sem informação.
27. `PATCH /admin/notices/{id}/facts/{fact_id}` marca o campo como `CONFIRMADO`, registra quem revisou e **sobrevive a uma nova análise** (a IA não sobrescreve correção humana).
28. `POST /admin/notices/{id}/confirm` só funciona após a análise terminar e registra quantos campos seguiam inferidos no momento da confirmação.
29. O Raio-X traz dias até a prova, disciplinas, assuntos, questões, vagas, salário, páginas, datas críticas, disciplinas mais extensas e pontos de atenção — **todos calculados em Python**, nenhum pedido ao modelo.
30. Pontos de atenção são derivados dos dados: campos não localizados, campos inferidos, regra eliminatória, TAF previsto e disciplinas sem conteúdo programático.
31. O candidato só enxerga o Raio-X de edital **confirmado**; enquanto está em análise, retorna 404.

## Qualidade
32. `pytest` verde (171 testes), incluindo pipeline completo com provedor de IA simulado, PDF gerado em memória, Qdrant local e os três caminhos do validador de citação.
33. `ruff` e `mypy` sem erro; `tsc`, `eslint` e `vitest` (37 testes) verdes no frontend.
34. Migração da Fase 3 aplica e reverte limpo; `docker compose config` válido com o serviço `qdrant` e a fila `documents` no worker.
