# Fase 1 — Vínculo de conteúdo e concurso principal

> Primeira fase do plano de evolução com agentes
> ([diagnóstico](27-evolucao-agentes-diagnostico.md)). É a fase que destrava as
> outras: sem ela, nada consegue dizer "este conteúdo é deste tópico".

## O problema que esta fase resolve

Questão e flashcard sempre souberam de qual tópico eram. **Aula e mapa mental
guardavam só texto livre.** Isso quebrava três coisas que o pedido exige:

- regenerar **só** o conteúdo afetado quando um edital é retificado;
- progresso por disciplina e tópico incluindo as aulas;
- domínio por tópico no painel do aluno.

E o painel pedia "concurso principal" e "dias restantes" sem que o candidato
jamais tivesse declarado qual concurso persegue.

## 1. A sugestão nunca aplica nada

1. O casamento entre o texto livre e o catálogo é calculado em
   `app/domain/catalog_match.py`: módulo **puro**, sem I/O, sem IA.
2. **Sem IA de propósito.** Comparar dois nomes é trabalho determinístico. Um
   modelo custaria token, variaria entre execuções e não seria auditável. Aqui
   a mesma entrada dá sempre a mesma saída, e a razão da nota é legível na
   tela — "nome idêntico", "um nome contém o outro", "palavras em comum".
3. A escada de notas é deliberada: igualdade vale mais que continência, que
   vale mais que palavras em comum. Nota alta por motivo fraco enganaria quem
   revisa.
4. Palavras que não distinguem nada são descartadas: "Noções de Direito
   Administrativo" e "Direito Administrativo" são a mesma disciplina.
5. **"Direito Constitucional" nunca casa forte com "Direito Administrativo"**,
   embora compartilhem uma palavra. É o caso que justifica o módulo existir:
   vincular ao tópico errado faria o aluno estudar a coisa errada achando que
   está no lugar certo.
6. **Lista vazia é resposta.** Quer dizer "o catálogo não tem isso", e quem
   revisa precisa ver isso em vez de receber o item menos ruim como se fosse o
   certo.
7. Empate é desfeito pelo nome, para a ordem não mudar entre duas leituras.
8. Quem confirma é uma pessoa, no painel (**Catálogo → Vínculos**). O conteúdo
   só muda de tópico depois disso.

## 2. A migração é aditiva

9. `training_lessons` e `mind_maps` ganharam `subject_id`/`topic_id` **anuláveis**.
   O texto livre continua lá e continua mandando na tela — o vínculo é para a
   plataforma saber de qual tópico a aula é, não para reescrever o que o autor
   digitou.
10. **Aula sem vínculo continua funcionando**, e isso é testado. "Não sei" é
    resposta melhor que um palpite errado.
11. O `subject_id` do mapa mental existia desde a fase passada e nunca era
    preenchido. Agora é, junto com o tópico.
12. Tópico de outra disciplina é recusado (`topic_subject_mismatch`): deixar
    passar criaria um vínculo impossível.
13. Vínculo pode ser desfeito — quem revisa precisa poder dizer "isto não é
    nada do catálogo" e seguir em frente.

## 3. Concurso principal e contagem regressiva

14. `profiles.primary_competition_id`: o candidato declara qual concurso
    persegue. É o que dá sentido ao painel.
15. **Sem dado real não há número**, a mesma regra da barra de FOCO da batalha:
    - sem concurso escolhido → sem contagem, com o motivo escrito;
    - sem data de prova no edital → sem contagem, com o motivo escrito.
16. Prova que já passou conta **zero**, nunca negativo.
17. Só concurso **publicado** pode ser escolhido: prender o candidato a uma
    ficha ainda em revisão exibiria dado que a equipe não terminou de conferir.
18. A escolha é por usuário e não vaza para outro — testado.

## 4. Esteira editorial do concurso

19. `competitions.editorial_status` com os cinco estados do pedido: rascunho →
    processamento → revisão → publicado → arquivado.
20. **É outro eixo que o `status` que já existia.** Aquele descreve o concurso
    no mundo (inscrições abertas, provas por vir); este descreve o nosso
    registro dele. Misturar os dois apagaria informação real — um concurso com
    inscrições abertas pode ter ficha ainda em rascunho aqui dentro.
21. **Uma verdade só:** publicar na esteira é o que torna o concurso visível.
    O `is_published` passou a ser o espelho, mantido em sincronia inclusive
    quando alguém o altera pelo `PATCH` antigo.
22. Publicado **não volta direto para rascunho**: sairia do ar sem ninguém
    revisar. Tem que passar por revisão ou ser arquivado.
23. O valor inicial em produção foi derivado do `is_published` que já estava
    lá, para nenhuma ficha publicada voltar para rascunho na migração.

## 5. Qualidade

24. **15 testes de domínio** no casamento, **19 de integração** (8 de vínculo,
    11 de foco e esteira) e **5 de tela**.
25. Migração sobe, desce e passa no `alembic check` sem divergência.
26. Os três estados do cartão de foco foram conferidos em imagem renderizada.

## O que esta fase **não** fez

- Não casou nenhuma aula antiga automaticamente. A fila de pendências está no
  painel esperando confirmação humana, que é exatamente o desenho.
- Não mexeu em questão nem flashcard: esses já tinham vínculo.
- Não criou o orquestrador nem o teto de custo — são a Fase 2.
