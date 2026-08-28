<div align="center">

# Concurso Mestre IA

**Transforme um edital em uma estratégia de preparação — e acompanhe o candidato até a prova.**

</div>

A plataforma responde continuamente a uma única pergunta:

> Considerando seu edital, banca, desempenho, erros, disponibilidade e tempo restante até a
> prova, **o que você deve estudar agora** para maximizar sua pontuação?

## Estado atual

**Fases 1 a 4** entregues e executáveis:

- **Fase 1:** arquitetura, Docker, FastAPI, MySQL, Redis, Celery, autenticação completa,
  sessões/dispositivos, RBAC, auditoria, LGPD, design system, casca da aplicação e painel
  administrativo.
- **Fase 2:** bancas, órgãos, concursos, cargos, disciplinas, árvore de assuntos, vínculo
  cargo×disciplina com peso, editais com upload verificado, catálogo público para o candidato
  — mais a **configuração de provedores de IA no painel** (chave cifrada, teste de conexão
  real, modelo por funcionalidade) e a **camada que evita pagar duas vezes pelo mesmo token**.
- **Fase 3:** análise de edital de ponta a ponta — extração do PDF (com OCR quando não há
  camada de texto), estruturação em trechos com página e posição, indexação vetorial no
  Qdrant, extração de campos com prompt versionado e, acima de tudo, **conferência de cada
  citação contra o documento**: sem citação verificada, o dado não vira fato. Acompanhamento
  ao vivo do processamento, revisão humana campo a campo e Raio-X do edital.
- **Fase 4:** plano de estudo gerado por cálculo (peso no edital, questões, extensão do
  conteúdo e sua disponibilidade real), missão diária, cronômetro com pausa, calendário,
  Modo Sprint e replanejamento que **não acumula dívida** — o que não cabe até a prova é
  declarado, não empilhado. Toda tarefa abre o "por quê?" com os números que a geraram.

- **Fase 5:** banco de questões com importação em lote, classificação sugerida pela IA que
  **só vale depois de revisada por uma pessoa**, resolução com o comentário de cada
  alternativa e simulados por tipo (oficial, da banca, dos erros, relâmpago, personalizado)
  com cronômetro, autosave e correção completa. Sem amostra suficiente, a taxa de acerto
  não é exibida; sem dados para o simulado pedido, a plataforma explica o que falta.

- **Fase 6:** mapa de incidência e DNA da banca calculados sobre o banco de questões,
  Priority Score cujas parcelas **somam exatamente** o número exibido (e que declara os
  sinais que ainda não existem, em vez de inflar o score), Caderno de Erros com causa
  declarada pelo candidato — a sugestão da IA só conta depois de confirmada — e Radar de
  Pegadinhas. O plano de estudo passa a se inclinar até 20% na direção do score.

- **Fase 7:** o **Mestre IA** responde a partir do edital analisado e dos seus números,
  com **citação conferida** em cada afirmação factual — o que não se sustenta no material
  aparece marcado como sem origem, e uma resposta inteiramente insustentada vira recusa
  explícita. Inclui Modo Professor, vocabulário com origem e vídeos conferidos por pessoas.

- **Fase 8:** flashcards com procedência declarada — cartão gerado por IA só entra se a
  citação existir literalmente no material, e o que não passa é descartado, não salvo com
  aviso. O motor de repetição espaçada reage a acerto, erro e velocidade, e **a fila nunca
  explode**: o que passa do teto diário é redistribuído, com o motivo dito em texto.

- **Gamificação (G1):** o **Mestre Game Engine** — XP com razão contábil auditável (todo
  ganho vira transação com motivo, e todo corte por teto é explicado), níveis, rank que
  mede **desempenho real** e não acúmulo (XP não entra na fórmula), sequência com proteção
  e sem linguagem de ameaça, missões diárias que nascem de sinal real e carregam o número
  que as gerou, e conquistas avaliadas sobre dados reais.

- **Gamificação (G2):** as telas comparativas. **Histórico de rank** com foto diária — o
  rank aparece subindo *e caindo*, ao lado do XP do mesmo período, porque acumular e
  dominar são coisas diferentes. **Você vs Banca**: o placar é a sua taxa de acerto real
  na banca do concurso-alvo, e os pontos dela são exatamente as questões que você errou —
  sem adversário simulado; disciplina com menos de 30 respostas não recebe placar.
  **Jornada da Aprovação**: marcos com critério verificável e o aviso, escrito na tela, de
  que eles medem cobertura e desempenho, não chance de aprovação. **Mapa do Edital**: cada
  disciplina como território, com o estado *pede revisão* para o que já foi dominado e
  está esfriando.

- **Gamificação (G3):** competição opcional e honesta. **Temporadas** com placar somado
  do próprio extrato de XP e recompensas de critério verificável — nada de caixa surpresa,
  e nenhum prêmio desbloqueia conteúdo de estudo. **Ligas** entre candidatos ao mesmo
  cargo, anônimas por padrão, desligáveis dos dois lados e que se recusam a virar tabela
  com menos de cinco participantes. E quatro **modos de desafio** — Boss Battle (contra a
  disciplina de maior Priority Score), Sobrevivência, Combo e Contra o Relógio — montados
  sobre questões reais do banco: sem questões suficientes, a rodada não acontece.

- **Gamificação (G4):** o momento em que os números saem da plataforma. **Duelos** em que
  os dois lados respondem exatamente as mesmas questões — sem adversário simulado, e com
  a vitória por ausência dita com esse nome. **Eventos** com metas medidas nas mesmas
  métricas do resto do sistema. **Modo Guerra**, um período intenso que o próprio
  candidato declara, com a meta confrontada com o histórico dele antes de começar e um
  acompanhamento que descreve sem acusar. E o **card compartilhável**: nada publicado por
  padrão, estatística sem amostra fica de fora com o motivo à vista, verificação literal
  contra qualquer promessa de aprovação, conteúdo congelado na publicação e link revogável.

As demais fases estão especificadas em [`docs/08-backlog-fases.md`](docs/08-backlog-fases.md)
e ainda **não** foram implementadas — a interface indica explicitamente o que está por vir,
sem telas ilustrativas nem dados fictícios.

### Conectar o ChatGPT (OpenAI)

`/admin` → aba **Inteligência** → *Conectar OpenAI (ChatGPT)* → informe a chave → *Testar
conexão* → *Importar modelos* → ative o provedor e escolha o modelo de cada funcionalidade.
A chave é cifrada antes de ir para o banco e nunca volta pela API. Nenhuma variável de
ambiente é necessária: a configuração é dado, não código.

## Documentação

| Documento | Conteúdo |
|---|---|
| [01 — Arquitetura](docs/01-arquitetura.md) | camadas, princípios, fluxo do edital, segurança |
| [02 — Estrutura de diretórios](docs/02-estrutura-diretorios.md) | backend e frontend, com o que é de cada fase |
| [03 — Diagrama de serviços](docs/03-diagrama-servicos.md) | topologia, contratos, jobs agendados |
| [04 — Modelagem MySQL](docs/04-modelagem-mysql.md) | tabelas, índices e decisões |
| [05 — Qdrant / RAG](docs/05-qdrant-rag.md) | coleções, chunking, recuperação híbrida, anti-alucinação |
| [06 — Intelligence Engine](docs/06-intelligence-engine.md) | portas, provedores, prompts versionados, custos |
| [07 — Wireframes](docs/07-wireframes.md) | Hoje, Raio-X do Edital e Mestre IA |
| [08 — Backlog das 10 fases](docs/08-backlog-fases.md) | escopo e critério de aceite de cada fase |
| [09 — Dependências](docs/09-dependencias.md) | bibliotecas por área |
| [10 — Docker](docs/10-docker.md) | imagens, ambientes e estratégia de build |
| [11 — Critérios de aceite da Fase 1](docs/11-criterios-aceite-fase1.md) | como verificar a fundação |
| [12 — Critérios de aceite da Fase 2](docs/12-criterios-aceite-fase2.md) | catálogo, IA configurável e cache |
| [13 — Critérios de aceite da Fase 3](docs/13-criterios-aceite-fase3.md) | pipeline de edital, prova de origem e Raio-X |
| [14 — Critérios de aceite da Fase 4](docs/14-criterios-aceite-fase4.md) | planejador, agenda, sessões e sprint |
| [15 — Critérios de aceite da Fase 5](docs/15-criterios-aceite-fase5.md) | banco de questões, prática e simulados |
| [16 — Critérios de aceite da Fase 6](docs/16-criterios-aceite-fase6.md) | incidência, DNA da banca, Priority Score e erros |
| [17 — Critérios de aceite da Fase 7](docs/17-criterios-aceite-fase7.md) | Mestre IA, citações conferidas e vocabulário |
| [18 — Critérios de aceite da Fase 8](docs/18-criterios-aceite-fase8.md) | flashcards, repetição espaçada e fila de revisão |
| [19 — Gamificação: arquitetura](docs/19-gamificacao-arquitetura.md) | Mestre Game Engine, XP, ranks, missões e wireframes |
| [20 — Critérios de aceite da Gamificação 1](docs/20-criterios-aceite-gamificacao-1.md) | XP auditável, antiabuso, rank, sequência e missões |
| [21 — Critérios de aceite da Gamificação 2](docs/21-criterios-aceite-gamificacao-2.md) | histórico de rank, Você vs Banca, jornada e mapa do edital |
| [22 — Critérios de aceite da Gamificação 3](docs/22-criterios-aceite-gamificacao-3.md) | temporadas, ligas por contexto e modos de desafio |
| [23 — Critérios de aceite da Gamificação 4](docs/23-criterios-aceite-gamificacao-4.md) | duelos, eventos, Modo Guerra e card compartilhável |

## Como executar

```bash
cp .env.example .env
# Gere uma SECRET_KEY forte:
python3 -c "import secrets; print(secrets.token_urlsafe(64))"

make up          # sobe mysql, redis, api, worker, beat, frontend e mailhog
make logs        # acompanha a inicialização
```

| Serviço | Endereço |
|---|---|
| Aplicação | http://localhost:5173 |
| API (Swagger) | http://localhost:8000/docs |
| Health / Readiness | http://localhost:8000/health · `/ready` |
| Caixa de e-mails (dev) | http://localhost:8025 |
| Qdrant (painel) | http://localhost:6333/dashboard |

O container da API aplica as migrations e executa o seed idempotente (papéis, permissões e
administrador inicial definido em `BOOTSTRAP_ADMIN_*`). **Troque a senha do administrador no
primeiro acesso.**

### Comandos úteis

```bash
make test        # testes do backend
make lint        # ruff + mypy
make migrate     # alembic upgrade head
make seed        # papéis, permissões e admin inicial
make fe-test     # testes do frontend
make help        # todos os comandos
```

## Princípios que o código segue

1. **Python calcula, a IA interpreta.** Score, percentual, ranking e data nunca saem de um LLM.
2. **Nada é inventado.** Todo dado exibido tem origem registrada — `OFICIAL`, `HISTÓRICO`,
   `GERADO POR IA` ou `ESTIMATIVA` — e a interface distingue os quatro.
3. **Token pago uma vez.** Resposta de IA e conhecimento de banca ficam gravados no banco com
   origem, amostra e validade; a IA só é chamada quando não existe registro válido.
4. **Explicabilidade.** Toda recomendação guarda o vetor de contribuições que a gerou.
5. **Nada hardcoded de negócio.** Planos, limites, features e prompts vivem no banco.
6. **HTTP não bloqueia.** Trabalho pesado vai para workers, com progresso em tempo real.
7. **Sem funcionalidade falsa.** Botão sem função e dado ilustrativo não entram no produto.

## Stack

Backend: Python 3.13 · FastAPI · SQLAlchemy 2 (async) · Alembic · MySQL 8 · Redis · Celery ·
Argon2 · JWT · Docker.
Frontend: React 19 · TypeScript · Vite · Tailwind CSS 4 · Radix (padrão shadcn/ui) ·
TanStack Query/Table · React Hook Form · Zod · Framer Motion · Lucide.
IA: camada `Concurso Intelligence Engine` com porta `AIProvider`, adaptador OpenAI,
prompts versionados, cache persistente, PyMuPDF + Tesseract para PDF/OCR e Qdrant para
busca vetorial.
