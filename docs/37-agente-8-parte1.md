# Agente 8 — parte 1: o analista que propõe e não aplica

> Implementação do desenho aprovado em
> [36-agente-8-desenho.md](36-agente-8-desenho.md), com as três decisões do dono
> do produto: **opção A** (sem acesso ao repositório), **credencial restrita
> junto** e **os quatro detectores** do primeiro corte.

## O que entrou

| Camada | Arquivo |
|---|---|
| Domínio puro: os quatro detectores | `app/domain/improvements.py` |
| Serviço: coleta, grava achado, reconcilia | `app/services/improvements.py` |
| Fábrica de sessão da credencial restrita | `app/db/session.py` |
| Duas tabelas (as únicas que ele escreve) | migração `9de7389084a8` |
| Painel administrativo | `features/admin/improvements/improvements-section.tsx` |
| Passo do orquestrador | `AgentKey.IMPROVEMENTS`, agora construído |
| Concessão da credencial em produção | passo 1.2 do `deploy-vps.yml` |

A chave `AgentKey.IMPROVEMENTS` estava declarada e **pulada com motivo escrito**
desde a Fase 2. Agora ela roda, e o catálogo deixou de trazer o
`pending_reason` — catálogo e registro contam a mesma história, e um teste cobra
isso.

## Os quatro detectores

| Chave | O que acha | Amostra mínima padrão |
|---|---|---|
| `SUSPECT_ANSWER_KEY` | questão com acerto muito abaixo do acaso | 30 respostas |
| `TOPIC_WITHOUT_MATERIAL` | tópico vinculado do edital sem questão, aula nem mapa | 1 tópico |
| `MODEL_ERROR_RATE` | funcionalidade cujo modelo falha acima do limiar | 20 chamadas em 7 dias |
| `ROUTE_INERT` | regra de roteamento ligada que nunca se aplicou | 50 avaliações em 30 dias |

Os limiares **moram no banco**: mudar um é salvar no painel, não publicar versão.

Dois merecem explicação.

**`SUSPECT_ANSWER_KEY` é medido contra o acaso, não contra um número absoluto.**
20% de acerto é desastre numa questão de quatro alternativas e é o esperado numa
de cinco com gabarito difícil. O limiar é `(1 ÷ alternativas) ÷ 2`, e a evidência
mais forte do achado vem de graça: *qual alternativa a maioria marcou*. Se 70%
marcaram a C e o gabarito aponta a A, o problema não é dificuldade.

**`ROUTE_INERT` separa os dois motivos**, porque a providência é diferente:
condição que nunca valeu é limiar errado; regra que fica sempre "não avaliada"
depende de um sinal que a funcionalidade não informa — e essa nunca vai valer,
não importa o limiar. O achado diz qual dos dois é.

## Os seis limites, e onde cada um está

**L1 — sem escrita em lugar nenhum.** O serviço escreve em
`improvement_findings` e `improvement_detector_settings`. Nenhuma chamada a
serviço de configuração, nem para aplicar o que ele mesmo propôs.

**L2 — sem acesso ao repositório.** Não há leitura de arquivo no serviço, e o
achado traz a proposta em texto apontando a tela que resolve. É a opção A da
decisão D1.

**L3 — nada se aplica sozinho.** Todo achado nasce `OPEN`. O painel tem "vou
fazer" e "recusar" — e nenhum botão que aplique a mudança. A frase está escrita
ao lado dos botões, para quem abre a tela não procurar o que não existe.

**L4 — credencial somente-leitura.** Ver a seção seguinte.

**L5 — sem amostra, sem achado.** Cada detector devolve `NOT_ENOUGH_DATA` com o
que falta, e isso vai para a ficha dele e para o relatório da varredura. **E
detector que não pôde rodar não fecha achado antigo** — é o teste que sustenta
esta parte: fechar ali diria que o problema acabou, quando o que acabou foi a
capacidade de medi-lo.

**L6 — economia só com número medido.** `measured_waste_cents` sai de
`ai_usage`. Quando o modelo não tem preço cadastrado, o achado escreve que o
desperdício **não pode ser estimado em dinheiro** — e nenhum "R$" aparece.

## A credencial restrita: o que ela garante, provado

A garantia em código é disciplina; a garantia de verdade é o banco recusando.
Com `MYSQL_READONLY_USER` e `MYSQL_READONLY_PASSWORD` no `.env`, o deploy cria
e mantém o usuário (passo 1.2, idempotente, depois das migrations porque a
concessão é por tabela).

Verifiquei num MySQL 8.4 real, com a mesma concessão que o deploy aplica:

| Tentativa do usuário restrito | Resultado |
|---|---|
| `SELECT` em `questions` | **permitido** |
| `INSERT` em `improvement_findings` | **permitido** |
| `INSERT` em `questions` | `ERROR 1142: INSERT command denied` |
| `DELETE` em `improvement_findings` | `ERROR 1142: DELETE command denied` |
| `DROP TABLE improvement_findings` | `ERROR 1142: DROP command denied` |

E a varredura inteira roda através dela: o relatório volta com
`isolation: DB_READONLY` e as fichas dos detectores são gravadas pelo próprio
usuário restrito.

**Não há volta silenciosa.** Credencial configurada que não conecta faz a
varredura **falhar** com mensagem própria — testado com senha errada. Cair na
credencial da aplicação ali usaria justamente o poder que o desenho tirou, e o
painel continuaria dizendo que está isolado.

Sem as variáveis, o analista roda na credencial da aplicação e tanto o painel
quanto o passo do orquestrador dizem **"garantia só do código"**. "Isolado" e
"isolado só no código" não são a mesma coisa, e a tela não deixa um parecer o
outro.

## O ciclo de vida de um achado

```
OPEN ──"vou fazer"──► ACCEPTED ──detector deixa de achar──► RESOLVED
  │                                                            │
  └──recusa (com motivo)──► REJECTED                     volta a achar
                                │                              │
                         prazo vence                           ▼
                                └──────────────────────────► OPEN (reaberto)
```

- **Impressão digital única:** a segunda passada atualiza e incrementa o contador
  de vezes vistas; não cria o segundo achado igual.
- **`RESOLVED` é verificado, não declarado.** A API **recusa** que uma pessoa
  feche um achado (`improvement_status_not_decidable`). Deixar declarar faria o
  painel mostrar problema resolvido que continua no ar.
- **Recusa exige motivo** e silencia aquela impressão digital pelo prazo do
  detector (90 dias por padrão, editável). Recusar e ser ignorado faria o
  administrador parar de recusar.
- **Reabertura é contada.** Um achado que volta depois de fechado mostra quantas
  vezes isso aconteceu.

## Nenhuma IA

Não há `AIFeature` nova, nem chamada a modelo, nem texto gerado. O desenho
previa a IA como redatora opcional dos achados; deixei de fora porque uma
funcionalidade de IA desligada por padrão e sem uso seria um botão sem função —
e porque o achado já sai legível com os números dentro. Se um dia a redação por
IA entrar, entra como funcionalidade própria no painel de IA, sujeita ao teto de
custo e ao roteador, com o texto marcado como gerado por IA.

## Como conferir

```bash
# Domínio: o que cada detector pode afirmar
pytest tests/unit/test_improvements_domain.py -q

# Ponta a ponta: achado, decisão, fechamento, reabertura e o que não fecha
pytest tests/integration/test_improvements.py -q

# O passo no orquestrador
pytest tests/integration/test_orchestrator.py -q -k improvements
```

No painel: **Administração → Melhorias**. Numa instalação sem dados, a varredura
não acha nada **e diz o que falta a cada detector**.

### O que foi verificado

| Verificação | Resultado |
|---|---|
| Migração `9de7389084a8` em SQLite | up / down / up, `alembic check` limpo |
| Migração em MySQL 8.4 real | up / down / up, carimbo em `(head)` |
| Concessão restrita em MySQL 8.4 real | permite o previsto, recusa o resto (tabela acima) |
| Varredura pela credencial restrita | `isolation: DB_READONLY` |
| Credencial errada | varredura falha, sem voltar para a credencial cheia |
| Backend | suíte completa verde |
| Frontend | 305 testes, ESLint, `npm run typecheck` e build limpos |

## O que esta parte não entrega

- **Os outros nove detectores** do desenho (seção 4 de docs/36). Entram quando
  este formato tiver sido usado.
- **Registro de recursos recusados** — simulado negado por falta de questões,
  resposta do tutor negada por falta de base. É o melhor sinal de prioridade de
  acervo que a plataforma poderia ter e hoje se perde. Continua sendo item
  separado, por ser mudança de instrumentação e não do agente.
- **Agendamento automático da varredura.** Ligar a periodicidade antes de ver o
  primeiro relatório é confiar em algo que ninguém leu. Hoje roda pelo painel ou
  como passo do orquestrador.
- **Proposta em forma de patch** (opção B da decisão D1). Fica para depois de o
  primeiro relatório existir e ser lido.
- **Comparação entre períodos.** Depende de histórico que o roteador ainda está
  acumulando.
