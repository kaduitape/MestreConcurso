# Fase 7 — árvore de conhecimento e inventário

> Item 16 do plano em [27-evolucao-agentes-diagnostico.md](27-evolucao-agentes-diagnostico.md):
> *"os dois itens de gamificação que faltam"*. Um deles não existia; o outro
> existia quase inteiro, e a seção final explica o que faltava de verdade nele.

## Parte A — a árvore de conhecimento

### O que ela acrescenta ao que já existia

O **Mapa do Edital** (`territory.py`, Gamificação 2) já mostra uma disciplina
por território, com cobertura, desempenho e retenção. A árvore desce um nível:
**dentro** da disciplina, qual tópico do conteúdo programático está medido,
qual está só começado e qual a plataforma não tem material para ensinar.

É a diferença entre saber que Português vai mal e saber que o problema é Crase.

A árvore **não tem tabela nova**. Nenhuma migração entrou nesta parte: cada
ramo é derivado na leitura das respostas, das revisões e do progresso real por
aula. Um contador paralelo por tópico seria mais rápido e poderia divergir do
que a pessoa de fato respondeu — e a plataforma inteira é construída na regra
oposta.

### A espinha é o edital, não o nosso catálogo

Os ramos saem de `notice_subjects` → `notice_topics` do **edital analisado** do
concurso principal, na ordem em que o edital escreveu. O catálogo é nosso; o
edital é da banca, e é dele que o candidato vai ser cobrado. Por isso o rótulo
que aparece na tela é o do edital, e cada disciplina carrega o peso, o número
de questões e a **procedência** (`OFFICIAL` quando saiu com citação conferida
no PDF, `INFERRED` quando foi deduzida) que a análise já produzia.

A medição de um ramo vem do tópico canônico vinculado **e dos descendentes
dele**: se o edital diz "Crase" e o catálogo tem "Crase antes de pronome"
embaixo, uma resposta no subtópico é uma resposta de crase e chega no ramo que
o candidato vê. O caminho materializado (`topics.path`) resolve isso com uma
consulta por sinal em vez de uma por tópico. O nó declara na tela quantos
subtópicos entraram na conta, para o número não parecer vindo só do rótulo
visível.

### As quatro regras de honestidade

**1. A árvore é a hierarquia do edital, não uma ordem de pré-requisitos.**

Um desenho de árvore sugere "só depois de passar por aqui". O edital **não
declara pré-requisito nenhum**, e inventar uma ordem pedagógica seria fabricar
conteúdo normativo — a mesma proibição que impede inventar peso ou data. O
aviso está escrito no topo da tela, não escondido num rodapé.

**2. Nenhum ramo tranca conteúdo.**

Não existe estado `LOCKED` neste domínio, e um teste cobra essa ausência. Todo
estado é descritivo: um tópico "não iniciado" está tão disponível quanto um
dominado. Travar matéria atrás de nível, liga ou pagamento é proibido no
projeto, e a árvore é exatamente o tipo de tela em que essa tentação aparece.

**3. Sem amostra não há porcentagem.**

Abaixo de **12 respostas** no ramo, não há taxa de acerto: há quantas respostas
ainda faltam para ela começar a significar algo. Taxa sobre três questões
oscila 33 pontos com uma resposta.

**4. Lacuna da plataforma não vira desempenho do candidato.**

Dois estados dizem que **nós** não medimos nada, e nenhum dos dois entra na
taxa de acerto nem na fila do que estudar:

| Estado | O que significa |
|---|---|
| `NOT_LINKED` | o tópico está no edital, mas ninguém ligou aquele texto a um tópico do catálogo — sem vínculo não há o que contar |
| `NO_MATERIAL` | vinculado, e a plataforma não tem questão, aula, mapa nem cartão dele |

`NOT_LINKED` é, aqui, o que `NOT_CHECKED` é para o auditor da Fase 3: ausência
de medição, não medição ruim. O tópico sem vínculo **não entra na média da
disciplina** — somá-lo como zero acerto faria a disciplina parecer pior do que
o candidato, atribuindo a ele uma falha de cadastro. É o teste que mais pesa
nesta fase.

Os dois estados aparecem num bloco próprio, com o texto *"isto é lacuna nossa,
não sua"*, e a tela diz que o conteúdo continua aberto para estudo por fora da
medição.

### Os estados que descrevem o candidato

| Estado | Critério |
|---|---|
| `NOT_STARTED` | há material e nenhuma atividade dele ainda |
| `IN_PROGRESS` | tocou no assunto, amostra insuficiente para medir |
| `MEASURED` | 12+ respostas, acerto abaixo de 75% |
| `MASTERED` | 12+ respostas, acerto de 75% ou mais |
| `NEEDS_REVIEW` | dominado e 21 dias sem nenhuma atividade |

`NEEDS_REVIEW` é o estado mais útil da árvore, pelo mesmo motivo que é no Mapa
do Edital: um tópico dominado que está esfriando parece verde em qualquer
gráfico de cobertura, e é por ali que a preparação vaza.

A disciplina **não tem medição própria** — a dela é a soma dos tópicos. Um
número próprio ao lado da soma dos filhos daria dois valores para a mesma
coisa, e eles divergiriam no primeiro tópico que faltasse.

### A fila do que estudar

`attention_order` devolve, nesta ordem: o que pede revisão, o que está medido
abaixo do domínio (pior acerto primeiro) e o que está em andamento. Tópico sem
vínculo e sem material **não entram** — a providência deles é de quem cadastra
conteúdo, e cobrá-la do candidato misturaria dois trabalhos diferentes.

## Parte B — o inventário, e o que faltava nele

O plano listava "inventário visual" como pendente. Ao abrir o código,
encontrei o **Arsenal** já pronto dentro da Batalha RPG: as quatro classes,
as nove peças nos três espaços, o cadeado nas que não foram conquistadas e o
nome da conquista que libera cada uma.

**Não construí uma segunda tela listando as mesmas peças.** Duplicar o arsenal
num "inventário" separado criaria dois lugares para editar a mesma coisa, e a
regra fundamental do projeto é não recriar o que já existe.

O que faltava de verdade era a **distância**. Um cadeado com o nome da
conquista ao lado ainda é quase uma armadilha: a pessoa não sabe se falta uma
questão ou novecentas. Agora cada peça travada mostra onde o candidato está —
`760 de 1.000` — com a barra correspondente, e os números saem da **mesma
avaliação que concede as conquistas**, não de uma segunda conta que poderia
divergir dela.

Com uma exceção deliberada: quando a conquista tem uma **guarda não atendida**
(uma métrica secundária que precisa valer junto), `ratio` vem nulo do domínio
de conquistas, e a tela **não desenha barra nenhuma** — escreve o motivo. O
progresso do contador sozinho, ali, faria a pessoa achar que está perto sem
estar. Essa decisão já era do domínio de conquistas; a tela passou a
respeitá-la.

## Um defeito de método que encontrei no caminho

O comando que eu vinha usando para conferir tipos no frontend,
`npx tsc --noEmit`, **não verifica nada neste projeto**: o `tsconfig.json` raiz
tem `files: []` e só aponta referências, que exigem `tsc -b`. O comando saía
com código 0 sem checar um arquivo.

O script correto é `npm run typecheck` (`tsc -b --noEmit`), e foi ele que
apontou quatro erros reais nesta fase — a fixture de teste do arsenal que não
tinha os campos novos. Nas fases anteriores a cobertura veio do `npm run build`
(`tsc -b && vite build`), que typecheca de verdade; então o resultado estava
certo mesmo com o comando errado. Daqui para frente, `npm run typecheck`.

## Como conferir

```bash
# Domínio: estado de cada ramo, soma por disciplina, fila de atenção
pytest tests/unit/test_knowledge_tree_domain.py -q

# Ponta a ponta: a árvore nascendo do edital, com os números reais
pytest tests/integration/test_knowledge_tree.py -q

# O arsenal com a distância até a conquista
pytest tests/integration/test_battle.py -q -k armory
```

Na aplicação: **Treinamento → Árvore do edital**. Sem concurso principal
escolhido ou sem edital analisado, a tela diz qual dos dois falta em vez de
desenhar uma árvore sem fonte.

### O que foi verificado

| Verificação | Resultado |
|---|---|
| Migrações | nenhuma — a árvore é derivada, sem tabela nova |
| Backend | suíte completa verde |
| Frontend | 294 testes, ESLint, `npm run typecheck` e build limpos |

## O que esta fase não entrega

- **Ordem de estudo sugerida pela árvore.** A fila de atenção ordena por
  desempenho medido, não por pré-requisito: a plataforma não tem essa
  informação, e o edital não a dá.
- **Terceiro nível na árvore.** O edital é plano dentro da disciplina; os
  subtópicos do catálogo entram **somados** ao ramo do edital, com a contagem
  declarada. Desenhá-los como um nível próprio apresentaria estrutura nossa
  como se fosse do edital.
- **Uma segunda tela de inventário.** Explicado acima: seria duplicata.
- **Tela para resolver as lacunas.** A árvore **mostra** o tópico sem vínculo
  e o sem material; vincular é a tela de vínculos da Fase 1 e gerar é o plano
  de geração da Fase 4. Não criei um terceiro caminho para a mesma coisa.
