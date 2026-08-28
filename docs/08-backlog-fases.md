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

## FASE 8 — Memorização  ✅ implementada
Flashcards com origem declarada (mão, IA com citação conferida, questão errada, erro do caderno), motor de repetição espaçada que reage a acerto, erro e **velocidade**, fila com teto diário e redistribuição, revisão relâmpago e estatística de memória.
**Aceite:** ver `docs/18-criterios-aceite-fase8.md`. Regra que sustenta a fase: **a fila nunca explode** — o excedente é redistribuído com o motivo declarado, e todo intervalo vem explicado.
Ainda não entra aqui: fila unificada com tópicos e vocabulário (depende da Fase 9) e curadoria de cartões globais.

## FASE 9 — Analytics  ✅ implementada
Mestre Score de 0 a 1000 com faixa de incerteza, "Se a prova fosse hoje", Caminho da Aprovação e os painéis de acerto, retenção, cobertura e consistência. O Modo Guerra saiu na G4.
**Aceite:** ver `docs/24-criterios-aceite-fase9.md`. Regra que sustenta a fase: **cada gráfico tem uma decisão associada e todo intervalo é visível** — e toda estatística nasce em Python determinístico, nunca na IA.
Ainda não entra aqui: comparação com nota de corte (depende de dado oficial que a plataforma não tem) e fila unificada de revisão com tópicos e vocabulário.

## FASE 10 — Comercial  ✅ implementada
Planos com direitos de uso vindos do banco, assinaturas com teste e tolerância, cupons, upgrade com crédito proporcional e downgrade agendado, porta de pagamento com Mercado Pago e webhook idempotente com assinatura verificada, limites de consumo aplicados nas telas de IA, faturamento e painel de SaaS.
**Aceite:** ver `docs/25-criterios-aceite-fase10.md`. Regra que sustenta a fase: **limite é dado, não código** — mudar um teto é um `UPDATE`. E cancelar não corta o que já foi pago.
Ainda não entra aqui: cobrança recorrente automática no adquirente, emissão fiscal e o teste em *sandbox* com credencial real, que é obrigatório antes de produção.

## Transversais (contínuos)
Segurança e LGPD (exportação/exclusão de conta desde a Fase 1), observabilidade, performance, PWA, acessibilidade AA, testes E2E a partir da Fase 4.

---

## GAMIFICAÇÃO — camada transversal

Projeto completo em `docs/19-gamificacao-arquitetura.md`.

### G1 — Motor, XP, níveis, sequência, missões e conquistas  ✅ implementada
Mestre Game Engine reativo a eventos, XP com razão contábil e antiabuso, níveis, rank de desempenho, sequência com proteção, missões diárias geradas de sinal real, conquistas, Central de Missões, perfil e painel de regras.
**Aceite:** ver `docs/20-criterios-aceite-gamificacao-1.md`. Regra que sustenta a camada: **XP mede esforço útil, rank mede desempenho, e nenhum dos dois mede cliques.**

### G2 — Ranks na interface comparativa, Você vs Banca, Jornada da Aprovação, Mapa do Edital
### G3 — Temporadas, ligas, Boss Battle, Sobrevivência, Combo, Contra o Relógio
### G4 — Desafio entre amigos, card compartilhável, eventos especiais e Modo Guerra
