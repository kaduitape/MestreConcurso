# Critérios de Aceite — Fase 2 (Catálogo) + Configuração de IA

## Configuração de provedores de IA (`/admin` → Inteligência)
1. Sem nenhum provedor cadastrado, a tela mostra estado vazio com a ação **Conectar OpenAI (ChatGPT)** — nada de campo decorativo.
2. Cadastrar um provedor cujo adaptador não existe é recusado com `ai_provider_unsupported` e a lista do que existe.
3. A chave é gravada **cifrada** (Fernet com chave derivada do `SECRET_KEY` por HKDF). Consultando `ai_providers` no banco, a chave em claro não aparece.
4. A API nunca devolve a chave: apenas `api_key_hint` (`sk-…7890`), data de cadastro e quem cadastrou.
5. **Testar conexão** faz chamada real ao provedor (`GET /v1/models`), grava status, latência e mensagem; falha de credencial vira `401 ai_provider_unauthorized`, limite vira `429`, indisponibilidade vira `503`.
6. **Importar modelos** popula `ai_models` apenas com o que a chave realmente acessa; modelos irrelevantes (áudio, imagem, moderação) são descartados; preço desconhecido fica vazio, nunca inventado.
7. Ativar um provedor sem chave é bloqueado (`ai_provider_missing_key`); remover a chave desativa o provedor.
8. Cada funcionalidade (`notice.extraction`, `board.profile`, `chat.tutor`, `question.classify`, `flashcard.generation`, `embeddings.default`, `rerank.default`) aparece na lista mesmo sem configuração, e só pode ser habilitada com modelo escolhido e provedor ativo.
9. Todas as ações (cadastro, chave, teste, sync, vínculo, limpeza de cache) ficam registradas em `audit_logs`.
10. Permissões `ai_settings:read` / `ai_settings:write` são exigidas; candidato recebe 403 e a tentativa é auditada.

## Persistência que evita gasto repetido de tokens
11. `ai_cache_entries` guarda a resposta por impressão digital de (funcionalidade + modelo + versão do prompt + entrada). A segunda chamada idêntica é servida do banco e incrementa `hits`.
12. A impressão digital ignora a ordem das chaves do JSON e muda quando muda o modelo ou a versão do prompt.
13. Entrada vencida não é servida; o painel mostra entradas, reaproveitamentos, **tokens economizados** e custo evitado, todos derivados dos contadores reais.
14. `board_knowledge_entries` guarda tudo o que for apurado sobre uma banca com origem (`COMPUTED`/`AI`/`EDITORIAL`/`OFFICIAL`), confiança, amostra (provas e questões), período, modelo, versão do prompt e tokens gastos — uma única vez.
15. Regravar o mesmo `(banca, tipo, chave)` atualiza o registro em vez de duplicar.
16. Registro vencido some para o candidato e continua visível ao administrador, marcado como vencido.
17. A tela do candidato lê o conhecimento gravado sem disparar nenhuma chamada de IA.

## Catálogo
18. CRUD completo de bancas, órgãos, concursos, cargos e disciplinas, com slug gerado automaticamente e único.
19. Banca vinculada a concursos não pode ser excluída (`409` informando quantos).
20. Cargo aceita vincular disciplinas com peso, número de questões e marcação de eliminatória; revincular a mesma disciplina atualiza em vez de duplicar.
21. Árvore de assuntos aceita até 4 níveis, mantém caminho materializado e remove a subárvore inteira ao excluir um nó.
22. Importação CSV (`assunto;subassunto;ordem`) cria a árvore, ignora repetidos e devolve contagem de criados/ignorados com os erros por linha.
23. Concurso em rascunho é invisível para o candidato: some da listagem e retorna 404 no detalhe.
24. Busca e filtros (texto, banca, ano, situação) funcionam no servidor, com paginação.

## Editais (cadastro e arquivo, sem IA)
25. Upload aceita **apenas PDF real**: content-type mentiroso é recusado pela assinatura do arquivo (`invalid_pdf`).
26. Arquivo acima do limite (`MAX_UPLOAD_SIZE_MB`) é recusado antes de qualquer gravação.
27. Nome do arquivo é gerado pela aplicação (ULID), gravado com permissão `0600` fora da árvore pública; `storage_key` manipulado não escapa do diretório de uploads.
28. Reenviar o mesmo arquivo (mesmo SHA-256) é recusado com `duplicate_notice_file` — o documento não é reprocessado nem repago na Fase 3.
29. Download exige autenticação e permissão; excluir o edital apaga os arquivos do armazenamento.

## Qualidade
30. `pytest` verde (118 testes) cobrindo cifra de segredos, adaptador OpenAI com transporte simulado, impressão digital do cache, validação de upload, CRUD do catálogo, permissões e fluxo de conhecimento da banca.
31. `ruff` e `mypy` sem erro; `tsc`, `eslint` e `vitest` (27 testes) verdes no frontend.
32. Migração `fase 2` aplica e reverte limpo; `docker compose config` válido.
