# Cadastro de concurso a partir do edital

> Cinco pedidos, na mesma direção:
>
> *"Faça um agente de IA, para cadastrar novos concursos: eu jogo uma URL, ela
> cadastra o edital, e cadastra todas as informações do concurso
> automaticamente."*
>
> *"Faça de eu subir o Edital e o sistema cadastrar todos os dados do concurso
> automaticamente."*
>
> *"faça cadastrar todos os cargos do edital, não só um"*
>
> *"agora cadastra os assuntos de cada disciplina também"*
>
> *"agora cadastra as datas do cronograma também"*

É o que está entregue. Sobe o PDF (ou cola o endereço), e o concurso aparece
cadastrado: a ficha do concurso, **todos os cargos** do edital, a grade de
disciplinas de cada um com peso e número de questões, os **assuntos** do
conteúdo programático e o **cronograma** com cada prazo. Sem ninguém digitar
nada.

Com uma linha, e ela é o coração deste documento: **o automático preenche
exatamente o que o edital sustenta por citação conferida caractere a caractere.
O que o edital não sustenta fica em branco e vai nomeado numa lista de
lacunas.** Por isso "cadastrado" nunca é apresentado como "completo" — a tela
mostra as duas contas lado a lado.

## Por que a linha está aí

1. Preencher um campo que a IA **deduziu** seria assinar no lugar de uma
   pessoa. E o cadastro de um concurso governa o estudo de quem usa a
   plataforma: data de prova, vagas, escolaridade, grade, o que cai. Um erro
   aqui não é um texto ruim que alguém ignora — é um candidato estudando a
   matéria errada para a prova errada.
2. Deixar o campo vazio com o motivo escrito custa **um clique** a quem
   cadastra. Preencher com palpite custa um concurso inteiro a quem estuda.
3. A entrada é um PDF que não é nosso. Desde a Fase 3 este projeto trata PDF
   recebido como **documento não confiável**: nada dentro dele é obedecido como
   instrução. Isso não muda porque o cadastro agora é automático — muda apenas
   quem aperta o botão.

Então o automático é agressivo onde pode ser (tudo que tem citação conferida
entra sozinho, inclusive cargo e grade) e silencioso onde não pode (o resto
fica em branco, com nome e motivo).

## As duas entradas

| Entrada | O que acontece |
|---|---|
| **Subir o PDF** | O arquivo passa pela validação de conteúdo (PDF é PDF, não executável renomeado) e vai direto para a análise. Não há link para escolher: o documento veio apontado. |
| **Colar o endereço** | Se o endereço já é um PDF, idem. Se é uma página, o serviço escolhe entre os PDFs de lá qual é o edital de abertura — por pontuação explicada — e **recusa escolher** quando nada se destaca. |

Dali para frente o caminho é **um só**. As duas entradas chegam ao serviço no
mesmo formato (`SourceDocument`), e nada depois disso sabe a diferença.

```
PDF (subido)  ─┐
               ├─▶ edital criado + PDF guardado com checksum
URL ─▶ escolha ┘   ─▶ análise da Fase 3 (citação conferida no texto)
                   ─▶ ficha campo por campo, com procedência
                   ─▶ CADASTRA: concurso + cargo + grade
                   └─▶ lacunas nomeadas, uma por uma
```

## O que o automático cadastra

4. **A ficha do concurso**: nome, ano, escolaridade, vagas, salário, início e
   fim das inscrições, data da prova. Entra como **rascunho não publicado** — a
   esteira editorial continua decidindo o que o candidato vê. O cadastro
   automático encurta o trabalho, não a conferência.
5. **Todos os cargos do edital**, um por cargo: nome, escolaridade, vagas,
   cadastro de reserva, salário, carga horária, requisitos, número de questões e
   duração da prova. Edital de concurso raramente tem um cargo só — tem vinte, e
   cadastrar um descartando dezenove apagaria da plataforma todo candidato que
   estuda para os outros.
6. **A grade de disciplinas de cada cargo**, com peso e número de questões.
   A disciplina do edital diz de qual cargo ela é; quando não diz, a grade é
   comum e vale para todos. Cada linha guarda de qual disciplina do edital veio,
   com nível de evidência e página.
7. **Os assuntos do conteúdo programático**, dentro de cada disciplina. É a
   unidade a que todo o estudo é endereçado — aula, questão, flashcard, plano,
   mapa mental. Sem assunto cadastrado, o conteúdo programático fica guardado
   como texto e não gera nada.
8. **O cronograma**, data por data: inscrições, taxa, isenção, prova, resultado,
   recursos, teste físico. Cada uma com a citação que a sustenta e a página.
9. **O estado do concurso**, derivado das datas: previsto, inscrições abertas,
   em andamento ou concluído. Antes disso todo concurso cadastrado nascia
   "previsto", inclusive os de inscrições abertas — informação errada na tela de
   quem procura concurso.
10. **O ano** é derivado da data oficial mais específica que houver (prova,
   depois início, depois fim das inscrições). Nenhum edital escreve "ano:
   2026", então derivar de data conferida é aritmética sobre dado do edital —
   enquanto chutar o ano corrente seria invenção. Sem nenhuma data conferida, o
   automático para.
11. **O órgão** é reaproveitado quando já existe no catálogo, com nome igual. Só
   é criado quando não existe.

## O cronograma: por que uma tabela nova, e não ler o edital

As datas já eram extraídas desde a Fase 3 — ficavam em `notice_events`, com
nível de evidência e página. O que não existia era cronograma **do concurso**.
Três razões decidiram por uma tabela própria em vez de a tela ler o edital:

12. **Retificação.** O concurso tem vários editais — abertura e retificações —, e
    é justamente a data que a retificação muda. Com as datas só no edital, o
    cronograma do concurso seria "o do edital que você consultou". Aqui cada
    data registra de qual edital veio, e a próxima pode substituí-la sem apagar
    de onde a anterior saiu.
13. **Correção humana.** Quem cuida do catálogo precisa poder corrigir uma data.
    O registro do edital é o **retrato do documento** desde a Fase 3: corrigir
    ali apagaria o que o documento dizia, que é o oposto do que ele serve. A
    coluna `source` distingue `NOTICE` de `MANUAL`.
14. **A pergunta é do concurso.** "Quando é a prova?" é pergunta sobre o
    concurso, não sobre um PDF. Obrigar a tela do candidato a entrar nas tripas
    do edital para respondê-la acoplaria o estudo à análise.

As três datas que já moravam em `competitions` (inscrições e prova) **continuam
lá** — são as que o plano de estudo lê, e movê-las quebraria tudo que as
consome. Elas entram **também** no cronograma, de propósito: a linha do tempo
não pode ter buraco justamente onde estão as datas mais importantes.

Duas coisas novas nessa conta:

15. **Data sem citação conferida não entra**, e fica nomeada. Prazo errado na
    tela é pior que prazo ausente: o candidato que confia numa data inventada
    perde a inscrição, e isso não se desfaz depois.
16. **O cronograma completa a ficha.** O edital diz as mesmas datas duas vezes:
    no texto corrido e no cronograma. Quando a citação do texto corrido não é
    localizada mas a do cronograma é, a data **tem** prova — só está em outro
    lugar do mesmo documento. Antes, o campo ficava em branco e a prova que
    existia era recusada. O campo em si continua marcado como inferido (a ficha
    não mente sobre a citação dele), e a data entra.

E uma correção de omissão antiga: `NoticeEvent` era a **única** coisa extraída
neste projeto que não guardava a própria citação. O nível de evidência dizia que
a data tinha prova, e a prova não ficava em lugar nenhum. Agora fica.

## Assunto: a única coisa que o serviço **cria** a partir de texto livre

Em todo o resto, este cadastro recusa criar o que não casa exatamente:
disciplina parecida não entra na grade, banca escrita num PDF não vira banca.
Com assunto é diferente, e a diferença tem um motivo.

**A fonte tem autoridade sobre a coisa.** Uma disciplina é global e
compartilhada entre concursos — "Direito Penal" é a mesma no concurso da PCDF e
no do TJ, e criar uma a partir do texto de um edital encheria um catálogo
compartilhado. O conteúdo programático **é** a lista oficial do que aquele
concurso cobra: é a única fonte que diz, com autoridade, quais assuntos caem.
Criar é obedecer ao edital; não criar seria guardar a lista e não usá-la.

Três regras governam cada item:

17. **Nome idêntico vincula, não duplica.** Assunto que já existe na disciplina é
   reaproveitado — senão o progresso do candidato se dividiria entre duas linhas
   que são a mesma coisa.
18. **Parecido cria, e declara o parecido.** "Crase" e "Emprego do sinal
   indicativo de crase" podem ser o mesmo assunto ou não. Decidir isso no chute
   mandaria o estudo para o lugar errado; recusar deixaria o edital sem a sua
   própria lista. Então o assunto entra, e junto vai o nome do parecido: *"Assunto
   novo em Língua Portuguesa: 'Emprego do sinal indicativo de crase' — parecido
   com 'Crase' que já existia (um nome contém o outro); confira se são o mesmo e
   junte, se forem."*
19. **Rótulo que não é um assunto não entra.** Um item com vários assuntos
    numerados numa linha ("1 Compreensão de textos. 2 Ortografia. 3 Crase") é
    uma extração que não dividiu a lista, não um assunto — viraria um item do
    plano de estudo que cobre três coisas e não fecha nunca. Idem para rótulo
    com menos de 3 ou mais de 200 caracteres.

E uma normalização que não é palpite: **a numeração do edital sai do nome.**
"1.1 Crimes contra a pessoa" vira "Crimes contra a pessoa", porque o "1.1" é a
numeração daquele edital — o próximo escreve outro número, e manter o prefixo
encheria o catálogo de duplicatas que só diferem nele. Número que é parte do
nome fica: "Lei nº 8.112/1990" e "Art. 5 da Constituição Federal" passam
intactos.

Duas coisas que esta parte **não** faz:

- **Não monta árvore.** Os assuntos entram no primeiro nível da disciplina. A
  extração devolve uma lista plana de textos, então não há hierarquia a perder —
  e deduzir a árvore pela numeração do edital é onde os erros se multiplicam.
- **Não cadastra assunto de disciplina que ficou fora da grade.** Assunto mora
  dentro de uma disciplina; sem a disciplina no catálogo, não há onde pôr. O
  motivo que aparece é o da disciplina, não um sobre assunto.

O `topic_id` de cada item do edital passa a apontar para o assunto do catálogo.
Além de ligar o estudo ao documento, isso melhora a retificação de graça: a
comparação de assuntos (Fase 5) já casava por `topic_id` quando ele existia, e
até agora ele nunca era escrito.

## Cargo é lista, e por que não virou campo

Os campos `position.*` da extração — nome, escolaridade, vagas, salário —
continuam existindo e descrevem o **cargo principal**. Eles não foram
transformados em lista, e isso é deliberado: o Raio-X e a comparação de
retificação os leem como valor único desde a Fase 3, e "qual é o cargo principal
deste edital" continua sendo uma pergunta legítima.

A lista de cargos entrou pelo caminho que o projeto já usava para disciplinas e
datas: uma chave nova na extração (`positions`) e uma tabela própria
(`notice_positions`), com citação, página e nível de evidência por cargo. O
prompt subiu para **v2** pedindo a lista; a impressão digital do cache inclui a
versão do prompt, então todo edital re-extrai na próxima análise — custo real de
IA, e o comportamento que a Fase 3 documentou.

Duas consequências que valem dizer:

- **Edital de cargo único continua cadastrando um cargo.** Quando o modelo não
  devolve lista — edital de um cargo, ou resposta de cache gerada pela v1 — o
  cargo principal é usado como lista de um item. Sem esse caminho de volta, um
  edital analisado antes desta mudança passaria a não ter cargo nenhum:
  regressão silenciosa no que já funcionava.
- **A coluna `position_label` das disciplinas, que existia e nunca era escrita,
  passou a ser escrita.** É ela que amarra "Banco de Dados" ao Analista de
  Tecnologia sem duplicar o conteúdo programático comum.

E um teto: **60 cargos por edital**. Acima disso o documento não é um edital de
concurso — é anexo de tabela de lotação, ou a extração se perdeu. Cadastrar
duzentos cargos por engano é mais caro de desfazer que de evitar.

## O que o automático não faz, e diz que não fez

20. **Campo sem citação conferida.** Inferido e não localizado ficam em branco,
   com o motivo de cada um ("a citação não foi localizada no PDF" / "o campo não
   foi encontrado no edital").
21. **Cargo sem citação conferida não vira cargo.** A regra de evidência vale
   para cargo como vale para qualquer outro campo: cargo que o modelo afirmou
   com citação que não existe no PDF fica de fora e é nomeado — um cargo
   inventado apareceria na tela do candidato como se fosse informação.
22. **Disciplina que não tem par exato no catálogo não entra na grade.** Aqui a
    regra é mais dura de propósito, e o motivo está no docstring do módulo de
    casamento: *casar "Direito Constitucional" com "Direito Administrativo"
    porque as duas começam igual é pior do que não casar nada — o aluno
    estudaria a disciplina errada achando que está no lugar certo*. Só **nome
    idêntico** (ou mesmas palavras distintivas) entra sozinho. As notas por
    continência e por palavras em comum continuam só sugerindo, e a lacuna diz
    qual era o mais próximo: *"não existe disciplina com este nome no catálogo.
    O mais próximo é 'Direito Penal Militar' (um nome contém o outro), mas
    parecido não basta para entrar sozinho."*
23. **Banca não é criada a partir de um nome escrito num PDF.** Se a banca do
    edital não está no catálogo, o concurso fica sem banca e a lacuna diz qual
    era e onde cadastrá-la. Criar banca assim encheria o catálogo de variações
    da mesma banca.
24. **A sigla do órgão é derivada das iniciais** — o edital não tem campo de
    sigla e a coluna exige um valor. "Polícia Civil do Distrito Federal" vira
    "PCDF". Isso é palpite de **rótulo**, não de fato do edital, e vai declarado
    como lacuna junto com a esfera, que entra como FEDERAL por padrão.

## As cinco travas que devolvem a decisão

Quando uma destas acontece, o estado para em `AWAITING_REVIEW`, o motivo fica
escrito na tela, e o formulário de revisão continua ali, inteiro:

25. **Nome do concurso sem citação conferida** — sem nome não há o que
    cadastrar.
26. **Órgão sem citação conferida e sem par no catálogo** — um concurso é
    sempre de alguém.
27. **Nenhuma data oficial conferida** — o ano sai dela.
28. **Concurso de mesmo nome e ano já no catálogo** — cadastrar de novo criaria
    duplicata. A tela mostra os parecidos.
29. **Análise falhou** — aí é `FAILED`, com o erro escrito. O edital e o PDF
    ficam gravados: repetir não baixa nem reprocessa nada.

Parar não é falha: é o automático dizendo o que não conseguiu decidir sozinho.
Quem preferir conferir **antes** de o concurso existir desliga a opção
"cadastrar automaticamente" no formulário — e aí o serviço monta a ficha e
espera.

## O que foi reaproveitado, inteiro

30. **O pipeline de análise de edital da Fase 3**, com a conferência literal de
    cada citação. Nada foi reescrito: o serviço cria o edital pelo
    `NoticeService` e chama o `NoticeAnalysisService.analyze` que a tela de
    editais já usava.
31. **O armazenamento de PDF** com validação de conteúdo e dedupe por checksum,
    e **a mesma validação** no upload direto.
32. **O catálogo** (`CatalogService`) e a auditoria que ele já gravava.
33. **O casamento determinístico de disciplina** (`app.domain.catalog_match`) —
    sem IA, auditável, mesma entrada dá sempre a mesma saída.
34. **Os níveis de evidência** e o selo visual da tela de editais
    (`EvidenceBadge`, `formatFactValue`). O que é oficial continua verde; o que
    a IA deduziu continua amarelo, aqui também.
35. **A medição e o teto de gasto de IA** da Fase 2.

O que é **novo** são as quatro coisas que não existiam: subir/buscar o
documento, escolher qual PDF é o edital, virar ficha conferida em cadastro, e
declarar o que ficou faltando.

## Um só criador

36. Os dois caminhos — automático e revisado — passam pelo mesmo `_register`.
    Ter um só lugar que cria é o que garante que o cadastro saia igual nos dois
    casos: a diferença entre eles é **de onde vêm os valores**, não do que
    acontece com eles. No automático, dos campos aplicáveis; no revisado, do
    pedido que a pessoa enviou.
37. `auto_applied` fica gravado na passagem, porque a pergunta "quem preencheu
    este campo?" tem resposta diferente nos dois casos, e quem audita precisa
    saber qual foi.

## As duas decisões puras

`app/domain/intake.py` não faz rede, banco nem IA.

### Que endereço pode ser buscado

38. Buscar uma URL que alguém digitou é deixar um estranho escolher o destino de
    uma requisição que **sai de dentro da rede**. A aplicação roda no mesmo host
    do banco e do Redis: `http://127.0.0.1:6379` ou
    `http://169.254.169.254/latest/meta-data` pediria ao próprio servidor que
    buscasse os segredos dele e devolvesse na tela.
39. O que o texto do endereço já condena é recusado **antes de gravar qualquer
    coisa** (HTTP 422): esquema que não é `http`/`https`, loopback, faixa
    privada, link-local, multicast, reservado, `localhost` e os nomes de
    metadados de nuvem.
40. O que depende de rede é conferido **depois do DNS**:
    `interno.exemplo.com` que resolve para `127.0.0.1` passaria por qualquer
    verificação feita só no texto. Essa recusa já é passagem, e fica registrada
    como `FAILED` com o motivo.
41. As travas valem em **cada salto** de redirecionamento — um site que responde
    `302` para a rede interna não ganha carona na permissão do endereço
    original. Mais duas: teto de 4 MB lido **durante** o download (para que dez
    gigabytes não virem dez gigabytes de memória) e 20 segundos por salto.
42. Subir o arquivo não passa por nada disso, porque não há endereço nenhum
    envolvido — é o caminho mais curto e também o mais seguro.

### Qual PDF é o edital

43. Uma página de concurso traz dez links: abertura, retificações, anexos,
    provas anteriores, gabaritos, resultado. Escolher "o primeiro PDF" acertaria
    às vezes — e errar aqui significa analisar a prova de 2019 e cadastrar um
    concurso inteiro a partir dela.
44. A escolha é por **pontuação explicada**: `edital de abertura` soma 5,
    `edital nº` soma 3; `retificação` tira 4, `gabarito` tira 5, `anexo` e
    `prova` tiram 3. Cada candidato guarda o que somou e o que subtraiu, em
    português. Acento e caixa não mudam nada.
45. **Quando nada se destaca, o serviço recusa escolher** (abaixo de 3 pontos, ou
    com menos de 2 de margem entre o primeiro e o segundo): estado
    `AWAITING_CHOICE`, candidatos listados com a nota, e a pessoa aponta.

## A passagem fica registrada

46. A tabela guarda a passagem inteira: de onde veio o documento, os PDFs que a
    página oferecia com a pontuação de cada um, qual foi escolhido e por quê, a
    ficha campo por campo com a citação, se o cadastro foi automático, o que
    ficou faltando, e o que a pessoa decidiu quando foi o caso.
47. Isso não é log por capricho. Quando alguém perguntar, em março, de onde veio
    a data que está na tela, a resposta precisa ser "deste PDF, desta citação na
    página 7" — e não "a IA leu em algum lugar".
48. As colunas em JSON são **instantâneos**, não dados relacionais: registram o
    que a tela mostrou no momento da decisão. Normalizá-las faria o registro
    mudar quando o catálogo mudasse, que é o oposto do que ele serve.
49. Quatro ações novas na auditoria: `INTAKE_STARTED`, `INTAKE_PROPOSED`,
    `INTAKE_APPLIED` (com `automatic` e a contagem de lacunas), `INTAKE_REJECTED`.

## Cinco erros encontrados ao escrever os testes

50. **A coleção de arquivos do edital vinha vazia para a análise.** O PDF era
    anexado depois de o edital já estar carregado na sessão e, com
    `expire_on_commit=False`, a coleção stale fazia a análise recusar com "Envie
    o PDF do edital antes de analisar". Correção: `session.refresh(notice,
    ["files"])`. O teste de integração pegou isso, não a leitura do código.
51. **A ficha vinha com todos os valores nulos.** A análise guarda o valor em
    `{"raw": ...}`, e eu lia `.get("value")`. O sintoma era cruel: o campo
    aparecia como `OFICIAL`, com citação e página corretas, e ainda assim não
    aplicável. Correção: `.get("raw")`, como `radiography.py` e
    `notice_diff.py` já faziam.
52. **O `auto_apply` do pedido era ignorado**, e `position_target` não saía na
    resposta. Nos dois casos o valor existia no serviço e morria na borda: a rota
    não repassava o parâmetro, e o schema de leitura não declarava o campo (o
    Pydantic descarta chave que não conhece). É o tipo de erro que nenhuma
    leitura de serviço encontra — só o teste que atravessa a borda.

E dois desta rodada. O primeiro: tirar a numeração do começo do rótulo
**quebrou a detecção de vários assuntos numa linha**. Com o "1 " inicial fora,
"1 Compreensão de textos. 2 Ortografia." passou a ter um marcador só e virou
assunto válido — exatamente o caso que a regra existia para barrar. A correção
separou as duas contas: o comprimento é medido no rótulo já limpo, a enumeração
é contada no rótulo **bruto**. "Art. 5 da Constituição Federal" tem um marcador
e é um assunto; dois ou mais são dois assuntos.

O segundo: inserir `position_label` no meio de `SubjectView` — um dataclass de
campos posicionais — quebrou o ajudante de um teste que já existia. A correção
não foi mexer no teste: foi mover o campo para o fim **com valor padrão
`None`**, que é o que ele é de verdade (nulo quer dizer "de todos
os cargos", o caso mais frequente). Teste quebrado às vezes é o desenho
avisando qual era o padrão certo.

## O que esta parte deixou de fora, e já se sabe onde dói

**Aplicar uma retificação ao cronograma.** O diff da Fase 5 compara as datas e
diz o que mudou; ninguém ainda **aplica** essa mudança ao cronograma do
concurso. A tabela foi desenhada para isso — cada data registra de qual edital
veio —, mas o fluxo de aplicar a retificação não existe. Até ele existir, uma
retificação que adia a prova aparece no diff e o cronograma continua com a data
antiga. É a lacuna mais afiada desta rodada, e está aqui escrita para não ser
descoberta por um candidato.

Houve também a armadilha já conhecida deste projeto: com `expire_on_commit=False`
é preciso atribuir **o objeto da relação**, não só a chave estrangeira —
`intake.notice = notice`, não `intake.notice_id = notice.id` — ou o carregamento
tardio acontece fora do laço assíncrono e estoura em `MissingGreenlet`.

## Onde fica na tela

**Admin → Catálogo → Cadastrar pelo edital**. Um botão "Subir o PDF do edital", um
campo para o endereço, e a opção "cadastrar automaticamente o que o edital
sustentar" ligada por padrão. Precisa das duas permissões de escrita
(`catalog:write` e `notices:write`), porque é o que a rota cria.

## O que foi verificado

| Verificação | Resultado |
|---|---|
| Travas de endereço e pontuação de PDF | 20 testes puros, sem rede |
| Busca com redirecionamento, teto de bytes e salto para rede interna | 8 testes com transporte injetado |
| Subir o edital → concurso + todos os cargos + grade de cada um | integração, conferindo campo a campo no catálogo |
| Edital com três cargos (um deles com CR) cadastra os três, cada um com seus números | integração |
| Grade por cargo: a comum entra em todos, a própria só no cargo dela | integração |
| Conteúdo programático virando assunto, com `topic_id` ligado ao edital | integração |
| Cronograma do concurso, cada data com citação e página | integração |
| Data sem citação conferida não entra e fica declarada | integração |
| O cronograma completando a ficha quando o campo escalar não tem citação | integração |
| O estado do concurso derivado das datas | integração + 5 testes puros |
| O candidato só vê o cronograma de concurso publicado | integração |
| O cronograma na tela, com prazo crítico e período | 2 testes de componente |
| Assunto que já existe é reaproveitado, não duplicado | integração |
| Assunto parecido entra e o parecido é declarado | integração |
| Rótulo com vários assuntos numa linha, ou curto demais, não entra | integração |
| A numeração do edital sai do nome do assunto | integração + 12 testes puros |
| Disciplina fora da grade não cadastra assunto nenhum | integração |
| Quantos assuntos de cada disciplina já existem no catálogo | 2 testes de componente |
| Cargo com citação inventada não entra e fica declarado | integração |
| Edital de cargo único continua cadastrando um (caminho de volta da v1) | integração + unitário |
| Cargos no Raio-X, com a soma de vagas rotulada como soma | 5 testes de componente |
| Retificação que acrescenta, remove ou muda cargo | 4 testes puros de comparação |
| As duas listas de escolaridade continuam iguais | unitário |
| As lacunas nomeadas (sigla derivada, banca fora do catálogo, disciplina sem par exato) | integração |
| As travas do automático (duplicata, nome sem citação conferida, automático desligado) | integração |
| Caminho por URL (página → PDF → análise → ficha → revisão → cadastro) | integração, com a rede dublada e o resto real |
| Arquivo que não é PDF, e candidato comum tentando subir | integração |
| Tela (as duas contas, campo em branco, recusa, descarte, duplicata, upload) | 13 testes de componente |
| Migração `e71d9a3c5f28` | up / down / up em **MySQL 8.4 real** e em SQLite, `alembic check` limpo |
| Backend | suíte completa verde |
| Frontend | `lint`, `typecheck` e `vitest` verdes |
| `mypy` | 36 erros pré-existentes, nenhum novo |

## O que esta parte não entrega

- **Retificação automática.** O diff da Fase 5 já sabe comparar, mas o cadastro
  não procura retificação sozinho.
- **Busca de concursos.** Ninguém sai procurando edital novo na internet: o
  documento é sempre informado por uma pessoa. Um rastreador seria outro
  projeto, com outra conversa sobre o que é legítimo buscar.
