# Mapas mentais medievais

> **Regra que governa esta parte:** o mapa é **dado estruturado**, não imagem.
> A IA produz painéis, itens e cores; a plataforma desenha a moldura; e cada
> palavra é texto de verdade na tela.

O pedido já previa o problema: *"caso o gerador de imagens não reproduza textos
com fidelidade, gere a arte sem os textos internos e insira-os posteriormente
por uma camada de texto programática."* É o que acontece aqui — e não só por
precaução.

## Por que o texto não é imagem
1. Gerador de imagem não escreve português confiável. Num mapa de estudo, texto
   embaralhado não é defeito estético: é **conteúdo errado sendo decorado**. Um
   "art. 37" que vira "ait. 3Z" na figura ensina uma coisa falsa a quem vai
   fazer prova.
2. Texto em DOM amplia no celular, é selecionável, pesquisável e audível por
   leitor de tela. Um alt-text não faz nada disso.
3. A arte medieval continua: moldura dourada com cantos em L (a mesma
   `.battle-frame` da Batalha RPG), fundo de pergaminho escuro, medalhão
   central e o rodapé com a marca e o lema.

## O conteúdo
4. Oito tipos de painel, fixos: **CONCEITO, REGRAS, CLASSIFICACOES, APLICACAO,
   EXCECOES, ERROS_COMUNS, MACETES, PEGADINHAS**. A IA cria só os que o assunto
   pede — painel sem conteúdo relevante é poluição.
5. Entre dois e oito painéis. Abaixo de dois não é mapa mental, é um cartão com
   título; acima de oito a tela deixa de ser lida.
6. Seis itens por painel, no máximo, e cada item é uma linha — não um parágrafo.
7. Os painéis saem sempre na mesma ordem de leitura, mesmo quando a IA responde
   fora de ordem. O mapa precisa ter espinha dorsal.
8. Tipo de painel inventado pela IA é descartado em silêncio: viraria painel sem
   cor nem sentido.

## As cores significam
9. O sistema é fixo e declarado: **azul** = conceito, **verde** = regra que vale,
   **roxo** = classificação, **vermelho** = proibição, erro e exceção,
   **dourado** = macete, **laranja** = pegadinha de banca.
10. Dentro do painel, cada item tem um **tom** — NEUTRO, CORRETO, INCORRETO ou
    ALERTA — que decide a cor da marca. É o que separa o exemplo certo do errado
    sem precisar escrever "errado:" na frente.
11. Cor que muda de significado entre dois mapas deixa de ser informação e vira
    enfeite, por isso a legenda vai impressa no rodapé do quadro.
12. As classes de cor são **literais no código**. O Tailwind 4 só emite a
    variável de tema que enxerga escrita: `border-${token}` montado em tempo de
    execução não gera cor nenhuma e o painel sai cinza. Já aconteceu duas vezes
    neste projeto.

## Nada é inventado
13. O prompt proíbe criar lei, artigo, súmula, data, prazo, autor ou definição
    que não esteja no material enviado.
14. Quando a IA tem dúvida, ela **não escreve o dado como certo**: registra a
    dúvida em `review_notes`, e a nota aparece em destaque para quem revisa.
15. O campo `source` de um item só é preenchido quando a fonte estava no
    material. Item sem fonte declarada aparece sem fonte — nunca com uma
    plausível.
16. O material enviado fica guardado junto com o mapa. Dá para conferir se o que
    saiu estava no que entrou.

## A IA propõe, uma pessoa publica
17. Gerar deixa o mapa em **READY**, nunca em PUBLISHED. Mapa mental é material
    de memorização: quem estuda vai decorar o que estiver escrito ali.
18. O estúdio edita texto e tom de cada item, remove item e remove painel, com
    pré-visualização do quadro exatamente como o candidato vai ver.
19. A revisão humana passa **pela mesma validação** da geração: mapa quebrado
    pela mão humana é recusado igual.
20. Mapa sem painel não é publicado.
21. No catálogo do candidato, o mapa publicado leva o rótulo **"Gerado por IA ·
    revisado"**. Quem estuda tem o direito de saber a origem do que está lendo.

## O token é pago uma vez
22. A impressão digital do cache inclui o prompt, o material enviado, o modelo e
    a versão do contrato do mapa. Gerar o mesmo mapa duas vezes não chama a API.
23. Mudar a estrutura do mapa invalida o que foi gerado com a estrutura antiga —
    é para isso que serve a versão no `fingerprint`.

## Falhas
24. Sem provedor de IA configurado, a geração é recusada **com o motivo**, e o
    mapa volta para rascunho em vez de ficar preso em "gerando" para sempre.
25. A última falha fica gravada e aparece no estúdio.

## Proporção e leitura
26. O quadro nasce **16:9** em tela larga, como o pedido pede, mas 16:9 é piso e
    não teto: cortar texto para caber na moldura seria esconder conteúdo de
    estudo. Mapa denso faz o quadro crescer.
27. No celular o quadro vira coluna única, com o medalhão no topo e os painéis
    na ordem de leitura. Sem rolagem horizontal.

## Configuração
28. É uma funcionalidade de IA como as outras: provedor e modelo são escolhidos
    no painel (`mindmap.generation`).

## Qualidade
29. 20 testes de domínio, 13 de integração e 7 de tela. Entre eles: que o texto
    do mapa é texto (e **nenhuma imagem** carrega conteúdo), que a cor de cada
    tipo é a fixa, que a fonte só aparece quando veio do material, que gerar
    duas vezes não paga duas vezes e que a geração sem provedor não trava o
    mapa.
30. Migração `mind_maps` sobe e desce limpa.
