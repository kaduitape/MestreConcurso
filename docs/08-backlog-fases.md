# 10. Backlog das 10 Fases

Cada fase termina com a aplicação **executável** (`docker compose up` → login → uso da feature) e com migrations, testes e documentação.

## FASE 1 — Fundação  ✅ implementada nesta entrega
- Monorepo, Docker Compose (mysql, redis, api, worker, beat, frontend), Makefile, `.env.example`.
- FastAPI: config tipada, logging estruturado, erros padronizados, request-id, security headers, CORS, rate limit Redis.
- MySQL + Alembic: users, profiles, roles, permissions, user_roles, role_permissions, user_sessions, auth_tokens, audit_logs, consent_logs.
- Auth: registro, verificação de e-mail, login, refresh rotativo com detecção de reuso, logout, logout remoto, dispositivos, recuperação de senha, troca de senha.
- RBAC por permissão + seed de papéis (`admin`, `staff`, `student`).
- Celery + fila de e-mail; e-mail com backends console/SMTP.
- Frontend: Vite + TS + Tailwind + design system, tema claro/escuro, AppShell, command palette, telas de auth, conta/dispositivos, admin básico (usuários, papéis, auditoria).
- Testes: unitários (senha, JWT, RBAC, rate limit) e integração (fluxo completo de auth, admin).

## FASE 2 — Concursos (catálogo)  ✅ implementada
Bancas, órgãos, concursos, cargos, disciplinas, árvore de assuntos (4 níveis, caminho materializado), vínculo cargo×disciplina com peso, upload de arquivos de edital com verificação de conteúdo (sem IA), CRUD admin, importação CSV de assuntos, busca e filtros, catálogo público só com o que está publicado.
Entrou junto, por decisão do produto: **configuração de provedores de IA no painel** (chave cifrada, teste de conexão real, importação de modelos, modelo por funcionalidade) e a **camada de persistência que evita gasto repetido de tokens** (cache de respostas por impressão digital + conhecimento de banca gravado com origem, amostra e validade).
**Aceite:** ver `docs/12-criterios-aceite-fase2.md`.

## FASE 3 — Edital IA  ✅ implementada
Pipeline PDF → extração (PyMuPDF) → OCR condicional (Tesseract, quando o PDF não tem camada de texto) → chunking com página e deslocamento → embeddings → Qdrant → extração estruturada com prompt versionado → **validação de citação em Python** → revisão humana → confirmação → Raio-X. Progresso ao vivo por SSE, alimentado pelo estado no banco (o worker roda em outro processo).
**Aceite:** ver `docs/13-criterios-aceite-fase3.md`. Regra que sustenta a fase: nenhum campo é `OFICIAL` sem citação conferida caractere a caractere no PDF; sem prova, é `INFERIDO` e sem página.

## FASE 4 — Estudo  ✅ implementada
Planejador determinístico (alocação por peso/questões/extensão, agenda por dia, composição por tipo de atividade, reta final automática), disponibilidade semanal, missão do dia, cronômetro com pausa, calendário de quatro semanas, replanejamento com teto diário e Modo Sprint.
**Aceite:** ver `docs/14-criterios-aceite-fase4.md`. Regra que sustenta a fase: o plano **nunca** vira pilha de atrasos — o que não couber até a prova é declarado como removido, não escondido.
Ainda não entra aqui: drag-and-drop no calendário e as camadas de edital/IA sobre a agenda (dependem das Fases 6 e 7).

## FASE 5 — Questões  ✅ implementada
Provas, questões, alternativas, comentários, importação em lote com relatório de erros, classificação assistida por IA **com revisão humana obrigatória**, filtros, resolução com correção comentada, simulados por tipo (oficial, banca, erros, relâmpago, personalizado) com cronômetro, autosave e correção completa por disciplina e dificuldade.
**Aceite:** ver `docs/15-criterios-aceite-fase5.md`. Regra que sustenta a fase: **nenhum percentual sem amostra** — abaixo de 20 respostas a taxa de acerto não é exibida, e quando falta dado para o simulado pedido a plataforma diz o motivo em vez de montar outro no lugar.
Ainda não entra aqui: cadernos de questões (entram com o Caderno de Erros). O simulado adaptativo foi fechado na Fase 6, quando o Priority Score passou a existir.

## FASE 6 — Inteligência  ✅ implementada
Mapa de incidência por banca, DNA da Banca calculado sobre o banco de questões, Priority Score com breakdown que soma o número exibido, Caderno de Erros com taxonomia fechada de causas (sugestão de IA só conta depois de confirmada), Radar de Pegadinhas e o simulado adaptativo guiado pelo score.
**Aceite:** ver `docs/16-criterios-aceite-fase6.md`. Regra que sustenta a fase: **nenhuma estatística sem amostra** — abaixo do mínimo o número não é publicado, e o motivo aparece no lugar dele.
Ainda não entra aqui: incidência e Priority Score por assunto (dependem de questões classificadas nesse nível) e o Mestre Score 0–1000 (Fase 9).

## FASE 7 — Mestre IA  ✅ implementada
Tutor com RAG sobre o edital analisado, transmissão do processamento por etapa, citação conferida em cada afirmação factual, Modo Professor, vocabulário inteligente com origem e catálogo de vídeos conferidos por pessoas.
**Aceite:** ver `docs/17-criterios-aceite-fase7.md`. Regra que sustenta a fase: **afirmação factual sem citação conferida não passa** — ela é marcada, e uma resposta inteiramente insustentada vira recusa.
Ainda não entra aqui: rerank cross-encoder, coleções além de `notices` e *function calling* aberto (as ferramentas são roteadas por regra).

## FASE 8 — Memorização
Flashcards (geração a partir de conteúdo/erro/questão/seleção), motor de repetição espaçada adaptativo, fila de revisão, revisão relâmpago. **Aceite:** intervalos reagem a acerto/erro/velocidade e a fila nunca "explode" após ausência.

## FASE 9 — Analytics
Mestre Score, "Se a prova fosse hoje", Caminho da Aprovação, dashboards (cobertura, retenção, consistência, evolução), Reta Final / Modo Guerra. **Aceite:** cada gráfico tem uma decisão associada; intervalos de confiança sempre visíveis.

## FASE 10 — Comercial
Planos, features/entitlements, assinaturas, trial, cupons, upgrade/downgrade, Mercado Pago + webhooks idempotentes, limites de consumo de IA, faturamento, dashboard SaaS (MRR, churn, ARPU, custo de IA). **Aceite:** ciclo completo assinar → cobrar → limitar → cancelar, com limites vindos do banco.

## Transversais (contínuos)
Segurança e LGPD (exportação/exclusão de conta desde a Fase 1), observabilidade, performance, PWA, acessibilidade AA, testes E2E a partir da Fase 4.
