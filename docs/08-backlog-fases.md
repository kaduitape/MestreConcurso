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

## FASE 2 — Concursos (catálogo)
Bancas, órgãos, concursos, cargos, disciplinas, árvore de assuntos, upload de arquivos de edital (sem IA), CRUD admin com TanStack Table, importação CSV, busca e filtros. **Aceite:** admin cadastra um concurso completo e o aluno o encontra na busca.

## FASE 3 — Edital IA
Pipeline PDF → extração → OCR condicional → chunking → embeddings → Qdrant → extração estruturada com evidência → tela de confirmação → Raio-X. WebSocket de progresso. **Aceite:** edital real de 80+ páginas processado com ≥ 90% dos campos com citação verificável e zero campo `OFICIAL` sem quote válida.

## FASE 4 — Estudo
Planner determinístico, disponibilidade semanal, tarefas diárias, cronômetro/sessões, calendário 3 camadas com drag-and-drop, replanejamento ao perder dias, Modo Sprint. **Aceite:** aluno com 12h/semana recebe plano coerente até a data da prova e o replanejamento não acumula dívida infinita.

## FASE 5 — Questões
Provas, questões, alternativas, comentários, importação, classificação assistida por IA com revisão humana, filtros, cadernos, execução de questões, simulados (todos os tipos) com cronômetro e autosave. **Aceite:** simulado oficial de 120 questões executado, salvo e corrigido.

## FASE 6 — Inteligência
Mapa de incidência, DNA da Banca, Priority Score com breakdown, Caderno de Erros com classificação de causa, Radar de Pegadinhas. **Aceite:** todo score exibido abre o "POR QUÊ?" com contribuições que somam o valor mostrado; nenhuma estatística sem amostra registrada.

## FASE 7 — Mestre IA
Tutor contextual com RAG, streaming, ferramentas, citações, Modo Professor, vocabulário inteligente, integração de vídeos verificada. **Aceite:** 100% das respostas factuais com citação resolvível; recusa explícita quando não há base.

## FASE 8 — Memorização
Flashcards (geração a partir de conteúdo/erro/questão/seleção), motor de repetição espaçada adaptativo, fila de revisão, revisão relâmpago. **Aceite:** intervalos reagem a acerto/erro/velocidade e a fila nunca "explode" após ausência.

## FASE 9 — Analytics
Mestre Score, "Se a prova fosse hoje", Caminho da Aprovação, dashboards (cobertura, retenção, consistência, evolução), Reta Final / Modo Guerra. **Aceite:** cada gráfico tem uma decisão associada; intervalos de confiança sempre visíveis.

## FASE 10 — Comercial
Planos, features/entitlements, assinaturas, trial, cupons, upgrade/downgrade, Mercado Pago + webhooks idempotentes, limites de consumo de IA, faturamento, dashboard SaaS (MRR, churn, ARPU, custo de IA). **Aceite:** ciclo completo assinar → cobrar → limitar → cancelar, com limites vindos do banco.

## Transversais (contínuos)
Segurança e LGPD (exportação/exclusão de conta desde a Fase 1), observabilidade, performance, PWA, acessibilidade AA, testes E2E a partir da Fase 4.
