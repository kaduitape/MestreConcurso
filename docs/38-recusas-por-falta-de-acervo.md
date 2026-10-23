# Agente 8 — parte 2: a recusa que a plataforma esquecia

> Item que ficou de fora do primeiro corte em
> [37-agente-8-parte1.md](37-agente-8-parte1.md), seção "o que esta parte não
> entrega": o registro de recursos recusados. É mudança de instrumentação, e por
> isso entrou separada do agente.

## O que estava se perdendo

A plataforma já recusava com honestidade em três lugares:

- **Simulado**: sem questões suficientes, ele não é montado. Não se repete
  enunciado para fechar o número.
- **Rodada de desafio**: o mesmo. Duplicar questão para completar 40 seria
  fabricar desafio.
- **Tutor**: sem base no material, ele se recusa a responder em vez de inventar.

Nos três casos o candidato recebia o motivo escrito — e a plataforma **esquecia
o fato**. Isso é o oposto de todo o resto do projeto: a recusa é o sinal mais
direto possível de "o que falta no acervo", porque não é opinião de ninguém. É
alguém tendo pedido algo que não existia.

Agora cada recusa vira uma linha em `resource_refusals`, e um detector do
analista transforma a repetição em prioridade de aquisição.

## O registro

`resource_refusals` é um log append-only, como `ai_usage`: uma linha por
recusa, nunca atualizada. Guarda o tipo, o código de erro, **o texto que o
candidato viu**, a variante (tipo de simulado ou modo de desafio), o candidato,
o concurso principal dele, a disciplina quando se sabe, e — quando o fluxo
trabalha com número — quanto foi pedido e quanto havia.

Guardar o texto mostrado evita que, meses depois, o painel explique a recusa de
um jeito diferente do que a pessoa recebeu.

### A parte que exige cuidado: a recusa levanta erro

Duas das três recusas levantam `ConflictError`. O erro sobe pela API e **a
transação da requisição é desfeita**. Gravar o registro na mesma sessão seria
gravá-lo para perdê-lo no rollback — o mesmo defeito que a medição de IA teve de
resolver na Fase 2.

Então `record_refusal` abre **sessão própria**, grava e confirma, antes de o
erro ser levantado. E, como em `record_usage`, falhar ao gravar não derruba o
fluxo: o candidato precisa receber a recusa explicada, não um erro de
contabilidade. O log avisa.

O teste `test_a_refused_simulation_is_recorded_even_though_the_request_failed`
é o que torna isso confiável: ele pede um simulado dos erros sem ter erros,
recebe 409 e confere que a linha **existe** no banco depois do rollback.

## O detector `REFUSED_RESOURCE`

Quinto detector do analista, mesma arquitetura dos outros quatro: determinístico,
sem IA, com janela e amostra mínima no banco.

Duas decisões de honestidade carregam o peso dele.

**Tentativas e pessoas são contadas separadamente.** Uma pessoa tentando quarenta
vezes não é quarenta pessoas, e a diferença muda a prioridade inteira. O achado
diz as duas coisas — *"12 tentativa(s) de 7 candidato(s) distinto(s)"* — e a
severidade sai do número de **pessoas**, não de tentativas.

**A idade do registro é declarada.** "Nenhuma recusa nos últimos 30 dias" soa
como acervo completo quando pode significar que a instrumentação tem dois dias
de vida. Quando o registro é mais novo que a janela, o detector escreve isso no
próprio texto do achado.

Além disso, o achado diz o pior caso medido — *"foram pedidas 30 questões e
havia 3"* — e a proposta deixa claro que isto **é pedido real, não suposição
sobre o que falta**. É a diferença entre este detector e o
`TOPIC_WITHOUT_MATERIAL`: aquele olha o edital e diz onde não há material; este
olha quem bateu na porta e não foi atendido.

## Sobre a credencial restrita

Nada muda. O usuário restrito do Agente 8 tem `SELECT` em todo o banco, então
lê `resource_refusals` sem concessão nova. **Escrever** nela é da aplicação, no
caminho da recusa, com a credencial normal — e é assim que deve ser: o analista
lê o que aconteceu, não produz o fato.

## Como conferir

```bash
# O detector: contagem de pessoas, idade do registro, pior caso
pytest tests/unit/test_improvements_domain.py -q -k refus

# Ponta a ponta: a recusa sobrevive ao rollback da requisição que falhou
pytest tests/integration/test_improvements.py -q -k refus
```

No painel: **Administração → Melhorias**, detector *Recurso recusado por falta
de acervo*. Numa instalação nova ele diz que não há recusa registrada — e, assim
que houver, diz quantas pessoas foram afetadas.

### O que foi verificado

| Verificação | Resultado |
|---|---|
| Migração `b717f6d45b01` em SQLite | up / down / up, `alembic check` limpo |
| Migração em MySQL 8.4 real | up / down / up, carimbo em `(head)` |
| Backend | suíte completa verde |
| `mypy` nos arquivos do analista | limpo (ver abaixo) |

## Dois consertos de tipo que vinham de trás

Ao rodar `mypy` corretamente nesta parte, apareceram erros em código que eu
havia escrito antes e declarado limpo:

- `app/services/improvements.py` reusava o nome `row` para dois tipos
  diferentes no mesmo método (um achado e a ficha de um detector), e fazia
  `int()` sobre duas colunas anuláveis.
- `app/services/game_battle.py` desempacotava um dicionário heterogêneo dentro
  de uma dataclass; agora a distância até a conquista é uma estrutura tipada.
- `app/domain/game/knowledge_tree.py` tinha um dicionário de prioridade
  inferido como indexado por enum e usado com `str`.

Nenhum deles mudava comportamento — os testes sempre passaram —, mas a minha
afirmação anterior de que `mypy` estava limpo nesses arquivos estava errada, e
a checagem que eu usei não os alcançou. Estão corrigidos, e o total do projeto
voltou aos 36 erros pré-existentes, nenhum em arquivo destas fases.

## O que esta parte não entrega

- **Os outros oito detectores** do desenho (docs/36, seção 4).
- **Recusa por teto de plano.** Quando o candidato bate no limite do plano
  gratuito, isso não é falta de acervo — é a cobrança funcionando. Misturar as
  duas coisas faria o analista pedir conteúdo onde o que houve foi um limite
  comercial.
- **Agendamento automático da varredura.**
- **Opção B da decisão D1** (proposta em forma de patch).
