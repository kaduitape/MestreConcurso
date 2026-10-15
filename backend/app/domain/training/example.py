"""A aula-modelo do Dia de Treinamento.

Serve a dois propósitos, e os dois justificam ela morar no código em vez de
nascer de um clique no estúdio:

*Uma instalação nova não começa vazia.* Quem abre a plataforma pela primeira
vez vê o formato funcionando de verdade — cenas, destaques, pergunta e
narração — em vez de uma tela de "nenhum treinamento publicado".

*É a referência do formato.* Quando alguém for escrever a próxima aula, tem um
exemplo completo do que cada campo faz: por que ``keywords`` precisa aparecer
no diálogo, o que ``emphasis`` muda na leitura, como uma cena de pergunta é
montada.

**O conteúdo é escrito à mão e conferido, não gerado por IA em tempo de
execução.** Crase é gramática consolidada: as regras aqui são as que as bancas
cobram, com os exemplos clássicos. Nada de estatística, de "a banca X cobra
isso em 70% das provas" ou de regra inventada para encher cena.
"""

from __future__ import annotations

from typing import Any

#: Identificador fixo (o tipo da coluna aceita até 26 caracteres). É estável de
#: propósito: o seed reconhece a aula-modelo por ele, e o link não muda entre
#: ambientes.
EXAMPLE_PUBLIC_ID = "exemplo-crase-treinamento"

EXAMPLE_SUBJECT = "Língua Portuguesa"
EXAMPLE_TOPIC = "Crase"
EXAMPLE_TITLE = "Crase: o acento que derruba candidato"
EXAMPLE_CHARACTER = "Mestre Arcanus"
EXAMPLE_LEVEL = "INTERMEDIARIO"
EXAMPLE_STYLE = "AULA"
EXAMPLE_DURATION_MINUTES = 12

#: As cenas. Cada termo listado em ``keywords`` aparece **literalmente** no
#: diálogo da mesma cena — é o que o player usa para acender o conceito na tela,
#: e um termo que não existe no texto não acenderia nada.
EXAMPLE_SCRIPT: dict[str, Any] = {
    "objectives": [
        "Reconhecer que a crase é a fusão da preposição com o artigo, e não um acento decorativo.",
        "Aplicar o teste da troca pelo masculino para decidir se o acento entra.",
        "Separar os casos em que a crase é proibida dos casos em que ela é obrigatória.",
        "Identificar as pegadinhas mais comuns de banca com o acento grave.",
    ],
    "scenes": [
        {
            "id": 1,
            "type": "intro",
            "narration": (
                "Saudações, aprendiz. Hoje enfrentamos um inimigo pequeno no tamanho e "
                "enorme no estrago: o acento grave. Ele cabe num traço, derruba candidato "
                "em prova inteira, e quase sempre por um motivo só — ninguém explicou o "
                "que ele realmente marca."
            ),
            "dialogue": (
                "Saudações, aprendiz. Hoje enfrentamos um inimigo pequeno no tamanho e "
                "enorme no estrago: o acento grave. Ele cabe num traço, derruba candidato "
                "em prova inteira, e quase sempre por um motivo só — ninguém explicou o "
                "que ele realmente marca."
            ),
            "screen_text": "Crase: o acento que derruba candidato",
            "keywords": ["acento grave"],
            "emphasis": ["acento grave"],
            "visual_elements": ["portao-antigo", "tocha"],
            "duration": 14,
            "transition": "fade",
            "character": {"emotion": "confident", "animation": "talking", "gesture": "explain"},
        },
        {
            "id": 2,
            "type": "explanation",
            "narration": (
                "Comece pelo começo: crase não é acento. Crase é a fusão de duas vogais "
                "iguais. Na prática que a prova cobra, é a preposição 'a' encontrando o "
                "artigo definido feminino 'a'. O acento grave é só a marca escrita desse "
                "encontro. Se não houver os dois, não há o que fundir — e não há acento."
            ),
            "dialogue": (
                "Comece pelo começo: crase não é acento. Crase é a fusão de duas vogais "
                "iguais. Na prática que a prova cobra, é a preposição 'a' encontrando o "
                "artigo definido feminino 'a'. O acento grave é só a marca escrita desse "
                "encontro. Se não houver os dois, não há o que fundir — e não há acento."
            ),
            "screen_text": "preposição a + artigo a = à",
            "keywords": ["crase", "preposição", "artigo definido"],
            "emphasis": ["fusão", "preposição", "artigo definido"],
            "visual_elements": ["duas-moedas-fundindo"],
            "duration": 18,
            "transition": "fade",
            "character": {"emotion": "serious", "animation": "talking", "gesture": "explain"},
        },
        {
            "id": 3,
            "type": "explanation",
            "narration": (
                "Daí saem duas perguntas, e você vai fazer as duas, sempre, nesta ordem. "
                "Primeira: o termo anterior exige a preposição 'a'? Quem assiste, assiste "
                "a alguma coisa. Quem se refere, refere-se a alguma coisa. Segunda: a "
                "palavra seguinte aceita o artigo feminino 'a'? Se as duas respostas forem "
                "sim, o acento entra. Se uma delas for não, ele não entra."
            ),
            "dialogue": (
                "Daí saem duas perguntas, e você vai fazer as duas, sempre, nesta ordem. "
                "Primeira: o termo anterior exige a preposição 'a'? Quem assiste, assiste "
                "a alguma coisa. Quem se refere, refere-se a alguma coisa. Segunda: a "
                "palavra seguinte aceita o artigo feminino 'a'? Se as duas respostas forem "
                "sim, o acento entra. Se uma delas for não, ele não entra."
            ),
            "screen_text": "1. O termo anterior pede 'a'?\n2. A palavra seguinte aceita 'a'?",
            "keywords": ["termo anterior", "palavra seguinte"],
            "emphasis": ["as duas", "sim", "não"],
            "visual_elements": ["duas-chaves"],
            "duration": 20,
            "transition": "slide",
            "character": {"emotion": "serious", "animation": "talking", "gesture": "point"},
        },
        {
            "id": 4,
            "type": "example",
            "narration": (
                "Existe um atalho honesto para isso, e ele quase nunca falha: troque a "
                "palavra feminina por uma masculina equivalente. Se aparecer 'ao', havia "
                "crase. Olhe: 'Vou à escola' vira 'Vou ao colégio' — apareceu 'ao', então "
                "o acento estava certo. Agora: 'Entreguei o relatório a você' vira "
                "'Entreguei o relatório a ele' — não apareceu 'ao', e por isso não há "
                "acento nenhum antes de pronome pessoal."
            ),
            "dialogue": (
                "Existe um atalho honesto para isso, e ele quase nunca falha: troque a "
                "palavra feminina por uma masculina equivalente. Se aparecer 'ao', havia "
                "crase. Olhe: 'Vou à escola' vira 'Vou ao colégio' — apareceu 'ao', então "
                "o acento estava certo. Agora: 'Entreguei o relatório a você' vira "
                "'Entreguei o relatório a ele' — não apareceu 'ao', e por isso não há "
                "acento nenhum antes de pronome pessoal."
            ),
            "screen_text": "Vou à escola → Vou ao colégio ✓\nEntreguei a você → a ele ✗",
            "keywords": ["troque a palavra feminina", "pronome pessoal"],
            "emphasis": ["ao", "Vou ao colégio", "a ele"],
            "visual_elements": ["balanca"],
            "duration": 22,
            "transition": "slide",
            "character": {"emotion": "encouraging", "animation": "talking", "gesture": "show"},
        },
        {
            "id": 5,
            "type": "explanation",
            "narration": (
                "Guarde agora a lista do que proíbe o acento, porque é dela que a banca "
                "tira metade das questões. Não há crase antes de palavra masculina, antes "
                "de verbo, antes de pronome pessoal e antes dos pronomes de tratamento "
                "iniciados por Vossa ou Sua — Vossa Senhoria não aceita artigo. Também não "
                "há diante de palavra no plural quando o 'a' está no singular: 'Não assisto "
                "a novelas'."
            ),
            "dialogue": (
                "Guarde agora a lista do que proíbe o acento, porque é dela que a banca "
                "tira metade das questões. Não há crase antes de palavra masculina, antes "
                "de verbo, antes de pronome pessoal e antes dos pronomes de tratamento "
                "iniciados por Vossa ou Sua — Vossa Senhoria não aceita artigo. Também não "
                "há diante de palavra no plural quando o 'a' está no singular: 'Não assisto "
                "a novelas'."
            ),
            "screen_text": (
                "Nunca: masculino · verbo · pronome pessoal · Vossa Senhoria · a + plural"
            ),
            "keywords": ["palavra masculina", "pronomes de tratamento", "plural"],
            "emphasis": ["Não há crase", "Vossa Senhoria", "a novelas"],
            "visual_elements": ["escudo-vermelho"],
            "duration": 22,
            "transition": "fade",
            "character": {"emotion": "warning", "animation": "talking", "gesture": "point"},
        },
        {
            "id": 6,
            "type": "explanation",
            "narration": (
                "E agora a outra metade: onde o acento é obrigatório. Nas locuções "
                "femininas, sempre — à noite, às pressas, à vista, à medida que, à moda de. "
                "E nas horas determinadas: 'A sessão começa às quatorze horas'. Repare que "
                "'à moda de' é a única exceção que permite acento antes de palavra "
                "masculina: 'bife à milanesa' é bife à moda milanesa."
            ),
            "dialogue": (
                "E agora a outra metade: onde o acento é obrigatório. Nas locuções "
                "femininas, sempre — à noite, às pressas, à vista, à medida que, à moda de. "
                "E nas horas determinadas: 'A sessão começa às quatorze horas'. Repare que "
                "'à moda de' é a única exceção que permite acento antes de palavra "
                "masculina: 'bife à milanesa' é bife à moda milanesa."
            ),
            "screen_text": "Sempre: locuções femininas · horas determinadas · à moda de",
            "keywords": ["locuções", "horas determinadas", "à moda de"],
            "emphasis": ["obrigatório", "às pressas", "à milanesa"],
            "visual_elements": ["ampulheta"],
            "duration": 22,
            "transition": "slide",
            "character": {"emotion": "confident", "animation": "talking", "gesture": "explain"},
        },
        {
            "id": 7,
            "type": "example",
            "narration": (
                "Veja o par que mais derruba gente na prova: 'Vendas a prazo' e 'Vendas à "
                "vista'. A mesma frase, o mesmo verbo, e só uma leva acento. Por quê? "
                "'Prazo' é masculino: não há artigo feminino para fundir. 'Vista' é "
                "feminino e forma locução adverbial: há. Não é decoreba — é a mesma regra "
                "aplicada duas vezes."
            ),
            "dialogue": (
                "Veja o par que mais derruba gente na prova: 'Vendas a prazo' e 'Vendas à "
                "vista'. A mesma frase, o mesmo verbo, e só uma leva acento. Por quê? "
                "'Prazo' é masculino: não há artigo feminino para fundir. 'Vista' é "
                "feminino e forma locução adverbial: há. Não é decoreba — é a mesma regra "
                "aplicada duas vezes."
            ),
            "screen_text": "Vendas a prazo ✗   ·   Vendas à vista ✓",
            "keywords": ["locução adverbial"],
            "emphasis": ["a prazo", "à vista", "masculino", "feminino"],
            "visual_elements": ["duas-placas"],
            "duration": 20,
            "transition": "slide",
            "character": {"emotion": "curious", "animation": "talking", "gesture": "show"},
        },
        {
            "id": 8,
            "type": "explanation",
            "narration": (
                "Três pegadinhas para fechar o cerco. Primeira: 'entrega a domicílio' não "
                "tem acento, porque domicílio é masculino — e muita gente acentua por "
                "ouvido. Segunda: 'a partir de' nunca tem acento, em nenhuma prova, em "
                "nenhum contexto. Terceira: nome de cidade só leva acento quando vem "
                "determinado. 'Vou a Brasília', mas 'Vou à Brasília dos anos sessenta'. "
                "O teste é simples: se você volta 'da' cidade, há crase; se volta 'de', não há."
            ),
            "dialogue": (
                "Três pegadinhas para fechar o cerco. Primeira: 'entrega a domicílio' não "
                "tem acento, porque domicílio é masculino — e muita gente acentua por "
                "ouvido. Segunda: 'a partir de' nunca tem acento, em nenhuma prova, em "
                "nenhum contexto. Terceira: nome de cidade só leva acento quando vem "
                "determinado. 'Vou a Brasília', mas 'Vou à Brasília dos anos sessenta'. "
                "O teste é simples: se você volta 'da' cidade, há crase; se volta 'de', não há."
            ),
            "screen_text": (
                "a domicílio ✗ · a partir de ✗ · Vou a Brasília / à Brasília dos anos 60"
            ),
            "keywords": ["a partir de", "determinado"],
            "emphasis": ["domicílio", "a partir de", "volta 'da'", "volta 'de'"],
            "visual_elements": ["armadilha"],
            "duration": 24,
            "transition": "fade",
            "character": {"emotion": "warning", "animation": "talking", "gesture": "point"},
        },
        {
            "id": 9,
            "type": "question",
            "narration": (
                "Hora de provar o que aprendeu. Em qual das alternativas o acento "
                "indicativo de crase está empregado corretamente?"
            ),
            "dialogue": (
                "Hora de provar o que aprendeu. Em qual das alternativas o acento "
                "indicativo de crase está empregado corretamente?"
            ),
            "screen_text": "Desafio do Mestre",
            "keywords": [],
            "emphasis": ["corretamente"],
            "visual_elements": ["pergaminho-selado"],
            "duration": 30,
            "transition": "cut",
            "character": {"emotion": "curious", "animation": "idle", "gesture": "ask"},
            "options": [
                "Encaminhei o processo à Vossa Senhoria ainda ontem.",
                "O pagamento do curso será feito à prazo, em seis parcelas.",
                "Entregamos o relatório à diretora às quatorze horas.",
                "Cheguei à Brasília no domingo de manhã.",
            ],
            "correct_option": 2,
            "feedback": (
                "A terceira está correta, e por dois motivos somados: 'entregar algo a "
                "alguém' exige a preposição, 'diretora' aceita o artigo feminino, e hora "
                "determinada pede o acento — às quatorze horas. Na primeira, pronome de "
                "tratamento iniciado por Vossa não aceita artigo: é 'a Vossa Senhoria'. Na "
                "segunda, 'prazo' é masculino: 'a prazo'. Na quarta, Brasília só levaria "
                "acento se viesse determinada, porque você volta 'de' Brasília, não 'da'."
            ),
        },
        {
            "id": 10,
            "type": "summary",
            "narration": (
                "Recolha o essencial. Crase é fusão, não enfeite. Duas perguntas resolvem "
                "quase tudo: o termo anterior pede 'a'? A palavra seguinte aceita 'a'? E "
                "quando a dúvida travar, troque pelo masculino e procure o 'ao'."
            ),
            "dialogue": (
                "Recolha o essencial. Crase é fusão, não enfeite. Duas perguntas resolvem "
                "quase tudo: o termo anterior pede 'a'? A palavra seguinte aceita 'a'? E "
                "quando a dúvida travar, troque pelo masculino e procure o 'ao'."
            ),
            "screen_text": "Fusão · duas perguntas · troca pelo masculino",
            "keywords": ["fusão"],
            "emphasis": ["duas perguntas", "troque pelo masculino"],
            "visual_elements": ["bau-fechando"],
            "duration": 16,
            "transition": "fade",
            "character": {"emotion": "confident", "animation": "talking", "gesture": "explain"},
        },
        {
            "id": 11,
            "type": "closing",
            "narration": (
                "É isso, aprendiz. O acento grave deixou de ser sorte e virou método. "
                "Leve as duas perguntas para a próxima prova e volte quando quiser treinar "
                "de novo — esta sala não fecha."
            ),
            "dialogue": (
                "É isso, aprendiz. O acento grave deixou de ser sorte e virou método. "
                "Leve as duas perguntas para a próxima prova e volte quando quiser treinar "
                "de novo — esta sala não fecha."
            ),
            "screen_text": "Disciplina • Estratégia • Aprovação",
            "keywords": [],
            "emphasis": ["método"],
            "visual_elements": ["tocha-apagando"],
            "duration": 14,
            "transition": "fade",
            "character": {"emotion": "happy", "animation": "talking", "gesture": "wave"},
        },
    ],
}
