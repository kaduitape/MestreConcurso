# Cadastro de concurso a partir do edital

> Dois pedidos, na mesma direção:
>
> *"Faça um agente de IA, para cadastrar novos concursos: eu jogo uma URL, ela
> cadastra o edital, e cadastra todas as informações do concurso
> automaticamente."*
>
> *"Faça de eu subir o Edital e o sistema cadastrar todos os dados do concurso
> automaticamente."*

É o que está entregue. Sobe o PDF (ou cola o endereço), e o concurso aparece
cadastrado: a ficha do concurso, o cargo e a grade de disciplinas com peso e
número de questões. Sem ninguém digitar nada.

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
5. **O cargo**: nome, escolaridade, vagas, salário, número de questões e
   duração da prova. Sem nome de cargo conferido, **nenhum cargo é criado** —
   um cargo chamado "Cargo" seria pior que nenhum, porque apareceria na tela do
   candidato como se fosse informação.
6. **A grade de disciplinas** do cargo, com peso e número de questões, montada
   das disciplinas que a análise extraiu do edital. Cada linha guarda de qual
   disciplina do edital veio, com nível de evidência e página.
7. **O ano** é derivado da data oficial mais específica que houver (prova,
   depois início, depois fim das inscrições). Nenhum edital escreve "ano:
   2026", então derivar de data conferida é aritmética sobre dado do edital —
   enquanto chutar o ano corrente seria invenção. Sem nenhuma data conferida, o
   automático para.
8. **O órgão** é reaproveitado quando já existe no catálogo, com nome igual. Só
   é criado quando não existe.

## O que o automático não faz, e diz que não fez

9. **Campo sem citação conferida.** Inferido e não localizado ficam em branco,
   com o motivo de cada um ("a citação não foi localizada no PDF" / "o campo não
   foi encontrado no edital").
10. **Disciplina que não tem par exato no catálogo não entra na grade.** Aqui a
    regra é mais dura de propósito, e o motivo está no docstring do módulo de
    casamento: *casar "Direito Constitucional" com "Direito Administrativo"
    porque as duas começam igual é pior do que não casar nada — o aluno
    estudaria a disciplina errada achando que está no lugar certo*. Só **nome
    idêntico** (ou mesmas palavras distintivas) entra sozinho. As notas por
    continência e por palavras em comum continuam só sugerindo, e a lacuna diz
    qual era o mais próximo: *"não existe disciplina com este nome no catálogo.
    O mais próximo é 'Direito Penal Militar' (um nome contém o outro), mas
    parecido não basta para entrar sozinho."*
11. **Banca não é criada a partir de um nome escrito num PDF.** Se a banca do
    edital não está no catálogo, o concurso fica sem banca e a lacuna diz qual
    era e onde cadastrá-la. Criar banca assim encheria o catálogo de variações
    da mesma banca.
12. **A sigla do órgão é derivada das iniciais** — o edital não tem campo de
    sigla e a coluna exige um valor. "Polícia Civil do Distrito Federal" vira
    "PCDF". Isso é palpite de **rótulo**, não de fato do edital, e vai declarado
    como lacuna junto com a esfera, que entra como FEDERAL por padrão.

## As cinco travas que devolvem a decisão

Quando uma destas acontece, o estado para em `AWAITING_REVIEW`, o motivo fica
escrito na tela, e o formulário de revisão continua ali, inteiro:

13. **Nome do concurso sem citação conferida** — sem nome não há o que
    cadastrar.
14. **Órgão sem citação conferida e sem par no catálogo** — um concurso é
    sempre de alguém.
15. **Nenhuma data oficial conferida** — o ano sai dela.
16. **Concurso de mesmo nome e ano já no catálogo** — cadastrar de novo criaria
    duplicata. A tela mostra os parecidos.
17. **Análise falhou** — aí é `FAILED`, com o erro escrito. O edital e o PDF
    ficam gravados: repetir não baixa nem reprocessa nada.

Parar não é falha: é o automático dizendo o que não conseguiu decidir sozinho.
Quem preferir conferir **antes** de o concurso existir desliga a opção
"cadastrar automaticamente" no formulário — e aí o serviço monta a ficha e
espera.

## O que foi reaproveitado, inteiro

18. **O pipeline de análise de edital da Fase 3**, com a conferência literal de
    cada citação. Nada foi reescrito: o serviço cria o edital pelo
    `NoticeService` e chama o `NoticeAnalysisService.analyze` que a tela de
    editais já usava.
19. **O armazenamento de PDF** com validação de conteúdo e dedupe por checksum,
    e **a mesma validação** no upload direto.
20. **O catálogo** (`CatalogService`) e a auditoria que ele já gravava.
21. **O casamento determinístico de disciplina** (`app.domain.catalog_match`) —
    sem IA, auditável, mesma entrada dá sempre a mesma saída.
22. **Os níveis de evidência** e o selo visual da tela de editais
    (`EvidenceBadge`, `formatFactValue`). O que é oficial continua verde; o que
    a IA deduziu continua amarelo, aqui também.
23. **A medição e o teto de gasto de IA** da Fase 2.

O que é **novo** são as quatro coisas que não existiam: subir/buscar o
documento, escolher qual PDF é o edital, virar ficha conferida em cadastro, e
declarar o que ficou faltando.

## Um só criador

24. Os dois caminhos — automático e revisado — passam pelo mesmo `_register`.
    Ter um só lugar que cria é o que garante que o cadastro saia igual nos dois
    casos: a diferença entre eles é **de onde vêm os valores**, não do que
    acontece com eles. No automático, dos campos aplicáveis; no revisado, do
    pedido que a pessoa enviou.
25. `auto_applied` fica gravado na passagem, porque a pergunta "quem preencheu
    este campo?" tem resposta diferente nos dois casos, e quem audita precisa
    saber qual foi.

## As duas decisões puras

`app/domain/intake.py` não faz rede, banco nem IA.

### Que endereço pode ser buscado

26. Buscar uma URL que alguém digitou é deixar um estranho escolher o destino de
    uma requisição que **sai de dentro da rede**. A aplicação roda no mesmo host
    do banco e do Redis: `http://127.0.0.1:6379` ou
    `http://169.254.169.254/latest/meta-data` pediria ao próprio servidor que
    buscasse os segredos dele e devolvesse na tela.
27. O que o texto do endereço já condena é recusado **antes de gravar qualquer
    coisa** (HTTP 422): esquema que não é `http`/`https`, loopback, faixa
    privada, link-local, multicast, reservado, `localhost` e os nomes de
    metadados de nuvem.
28. O que depende de rede é conferido **depois do DNS**:
    `interno.exemplo.com` que resolve para `127.0.0.1` passaria por qualquer
    verificação feita só no texto. Essa recusa já é passagem, e fica registrada
    como `FAILED` com o motivo.
29. As travas valem em **cada salto** de redirecionamento — um site que responde
    `302` para a rede interna não ganha carona na permissão do endereço
    original. Mais duas: teto de 4 MB lido **durante** o download (para que dez
    gigabytes não virem dez gigabytes de memória) e 20 segundos por salto.
30. Subir o arquivo não passa por nada disso, porque não há endereço nenhum
    envolvido — é o caminho mais curto e também o mais seguro.

### Qual PDF é o edital

31. Uma página de concurso traz dez links: abertura, retificações, anexos,
    provas anteriores, gabaritos, resultado. Escolher "o primeiro PDF" acertaria
    às vezes — e errar aqui significa analisar a prova de 2019 e cadastrar um
    concurso inteiro a partir dela.
32. A escolha é por **pontuação explicada**: `edital de abertura` soma 5,
    `edital nº` soma 3; `retificação` tira 4, `gabarito` tira 5, `anexo` e
    `prova` tiram 3. Cada candidato guarda o que somou e o que subtraiu, em
    português. Acento e caixa não mudam nada.
33. **Quando nada se destaca, o serviço recusa escolher** (abaixo de 3 pontos, ou
    com menos de 2 de margem entre o primeiro e o segundo): estado
    `AWAITING_CHOICE`, candidatos listados com a nota, e a pessoa aponta.

## A passagem fica registrada

34. A tabela guarda a passagem inteira: de onde veio o documento, os PDFs que a
    página oferecia com a pontuação de cada um, qual foi escolhido e por quê, a
    ficha campo por campo com a citação, se o cadastro foi automático, o que
    ficou faltando, e o que a pessoa decidiu quando foi o caso.
35. Isso não é log por capricho. Quando alguém perguntar, em março, de onde veio
    a data que está na tela, a resposta precisa ser "deste PDF, desta citação na
    página 7" — e não "a IA leu em algum lugar".
36. As colunas em JSON são **instantâneos**, não dados relacionais: registram o
    que a tela mostrou no momento da decisão. Normalizá-las faria o registro
    mudar quando o catálogo mudasse, que é o oposto do que ele serve.
37. Quatro ações novas na auditoria: `INTAKE_STARTED`, `INTAKE_PROPOSED`,
    `INTAKE_APPLIED` (com `automatic` e a contagem de lacunas), `INTAKE_REJECTED`.

## Três erros encontrados ao escrever os testes

38. **A coleção de arquivos do edital vinha vazia para a análise.** O PDF era
    anexado depois de o edital já estar carregado na sessão e, com
    `expire_on_commit=False`, a coleção stale fazia a análise recusar com "Envie
    o PDF do edital antes de analisar". Correção: `session.refresh(notice,
    ["files"])`. O teste de integração pegou isso, não a leitura do código.
39. **A ficha vinha com todos os valores nulos.** A análise guarda o valor em
    `{"raw": ...}`, e eu lia `.get("value")`. O sintoma era cruel: o campo
    aparecia como `OFICIAL`, com citação e página corretas, e ainda assim não
    aplicável. Correção: `.get("raw")`, como `radiography.py` e
    `notice_diff.py` já faziam.
40. **O `auto_apply` do pedido era ignorado**, e `position_target` não saía na
    resposta. Nos dois casos o valor existia no serviço e morria na borda: a rota
    não repassava o parâmetro, e o schema de leitura não declarava o campo (o
    Pydantic descarta chave que não conhece). É o tipo de erro que nenhuma
    leitura de serviço encontra — só o teste que atravessa a borda.

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
| Subir o edital → concurso + cargo + grade cadastrados | integração, conferindo campo a campo no catálogo |
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

- **Conteúdo programático virando tópicos do catálogo.** A grade de disciplinas
  entra; os **assuntos** dentro de cada disciplina (que a análise extrai e
  guarda no edital) não viram `Topic`. Criar árvore de tópicos a partir de texto
  livre tem o mesmo problema de casamento das disciplinas, multiplicado por
  dez — e aqui o estrago de errar é maior, porque é a quem o estudo é
  endereçado. Próximo passo natural, com a mesma regra: só nome idêntico.
- **Mais de um cargo por edital.** Edital com vinte cargos cadastra **um**, o
  que a análise extraiu em `position.name`. A extração da Fase 3 tem um cargo
  por edital no contrato; mudar isso é mexer no prompt versionado e nas telas
  que já leem esse campo.
- **Retificação automática.** O diff da Fase 5 já sabe comparar, mas o cadastro
  não procura retificação sozinho.
- **Busca de concursos.** Ninguém sai procurando edital novo na internet: o
  documento é sempre informado por uma pessoa. Um rastreador seria outro
  projeto, com outra conversa sobre o que é legítimo buscar.
