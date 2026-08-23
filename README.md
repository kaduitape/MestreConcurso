<div align="center">

# Concurso Mestre IA

**Transforme um edital em uma estratégia de preparação — e acompanhe o candidato até a prova.**

</div>

A plataforma responde continuamente a uma única pergunta:

> Considerando seu edital, banca, desempenho, erros, disponibilidade e tempo restante até a
> prova, **o que você deve estudar agora** para maximizar sua pontuação?

## Estado atual

**Fase 1 — Fundação** entregue e executável: arquitetura, Docker, FastAPI, MySQL, Redis,
Celery, autenticação completa, sessões/dispositivos, RBAC, auditoria, LGPD, design system,
casca da aplicação e painel administrativo básico.

As demais fases estão especificadas em [`docs/08-backlog-fases.md`](docs/08-backlog-fases.md)
e ainda **não** foram implementadas — a interface indica explicitamente o que está por vir,
sem telas ilustrativas nem dados fictícios.

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
| [11 — Critérios de aceite da Fase 1](docs/11-criterios-aceite-fase1.md) | como verificar a entrega |

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
3. **Explicabilidade.** Toda recomendação guarda o vetor de contribuições que a gerou.
4. **Nada hardcoded de negócio.** Planos, limites, features e prompts vivem no banco.
5. **HTTP não bloqueia.** Trabalho pesado vai para workers, com progresso em tempo real.
6. **Sem funcionalidade falsa.** Botão sem função e dado ilustrativo não entram no produto.

## Stack

Backend: Python 3.13 · FastAPI · SQLAlchemy 2 (async) · Alembic · MySQL 8 · Redis · Celery ·
Argon2 · JWT · Docker.
Frontend: React 19 · TypeScript · Vite · Tailwind CSS 4 · Radix (padrão shadcn/ui) ·
TanStack Query/Table · React Hook Form · Zod · Framer Motion · Lucide.
IA (a partir da Fase 3): camada `Concurso Intelligence Engine` com provedores intercambiáveis
e Qdrant como banco vetorial.
