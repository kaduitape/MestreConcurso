# Fase 5 — Retificação de edital

> Quinta fase do [plano de evolução](27-evolucao-agentes-diagnostico.md):
> *"diff entre versões de edital; marcar o que mudou; regenerar só o afetado."*

## O problema

Retificação é rotina em concurso: muda data, muda peso, entra disciplina, sai
tópico. O problema nunca foi a mudança — é **ninguém saber que ela aconteceu**,
e o conteúdo continuar apontando para um programa que não existe mais.

## Diagnóstico: o que já existia

1. `NoticeKind.RECTIFICATION` já existia, e cada edital já virava uma análise
   própria — disciplinas, tópicos, datas e dados, cada um com o nível de
   evidência. Nada disso foi reescrito.
2. O que faltava era **comparar duas análises** e dizer o que mudou.
3. A Fase 1 ligou conteúdo ao tópico canônico; é esse vínculo que permite saber
   qual aula um tópico removido deixa órfã. A Fase 4 fez o plano de geração
   pular o que já existe; é por isso que "regenerar só o afetado" não precisou
   de código novo.

## Três regras

4. **Nenhuma IA.** A comparação é entre duas análises que já existem. Comparar
   rótulo com rótulo é determinístico; pedir a um modelo que "resuma o que
   mudou" trocaria um fato por uma opinião que não se repete.
5. **Nada é apagado.** Tópico que saiu do edital deixa o conteúdo **órfão**,
   com o motivo escrito — nunca removido, nunca proposto para remoção. A tela
   não tem botão de apagar, de propósito: um edital retificado pode ser
   retificado de novo.
6. **A procedência viaja junto.** Cada mudança carrega o nível de evidência do
   dado novo. Data conferida no PDF recebe selo verde; data que a IA deduziu
   recebe selo de aviso, e o laudo conta quantas são. Repassar dedução como
   oficial seria o jeito mais fácil de a plataforma mentir.

## O que a comparação enxerga

7. **Disciplinas** — entrada, saída e mudança de peso ou número de questões (a
   distribuição do plano de estudo muda com eles).
8. **Tópicos** — entrada e saída do conteúdo programático.
9. **Datas** — onde a retificação mais dói no candidato: cada mudança mostra a
   data velha e a nova lado a lado.
10. **Dados do edital** — vagas, salário, requisitos: valor antigo e novo.
11. O casamento é pelo **vínculo com o catálogo** antes do texto: o edital pode
    reescrever "Língua Portuguesa" como "Português" sem que nada tenha mudado
    de verdade.

## O impacto, e o que fazer com ele

12. Conteúdo de tópico removido → **órfão**, com o aviso de que quem decide o
    destino dele é uma pessoa.
13. Tópico novo sem conteúdo → **falta**, e o próximo plano de geração o
    inclui. "Regenerar só o afetado" sai de graça porque a Fase 4 já pula o
    que existe: um plano montado depois da retificação contém exatamente os
    tópicos novos.
14. Tópico novo que **já tem conteúdo** não aparece como falta. É o
    reaproveitamento da Fase 4 valendo também aqui.
15. Comparar não é o mesmo que ler: a comparação pode ser marcada como lida,
    para uma retificação já tratada não sumir no meio das outras.

## O que a comparação recusa

16. Concurso com **uma só versão analisada** não é comparado. Comparar com o
    vazio diria que o edital inteiro é novidade — e uma tela cheia de "entrou"
    falso é pior que uma tela vazia.

## Qualidade

17. **15 testes de domínio** e **10 de integração**. Entre eles: que a aula de
    um tópico removido continua publicada depois da comparação, que o nível de
    evidência chega à tela, que renomear disciplina ligada ao mesmo catálogo
    não é mudança, e que um tópico novo com conteúdo não vira falta.
18. Migração `notice_diffs` sobe, desce e passa no `alembic check`.
19. A tela foi conferida em imagem renderizada.

## O que esta fase não entrega

- **Aviso ao candidato.** Hoje a retificação aparece no painel administrativo.
  Mostrar ao aluno que o concurso dele mudou de data é uma decisão de produto
  que não foi tomada — e inventá-la de passagem seria mexer na experiência de
  quem estuda sem ninguém pedir.
- **Arquivar o conteúdo órfão em lote.** O caminho existe (o Estúdio arquiva),
  mas em lote isso vira "apagar com outro nome". Fica como decisão humana,
  item a item.

> **Atualização (out/2026) — a comparação passou a cobrir cargos.** Com os
> cargos do edital virando lista própria (ver
> [cadastro pelo edital](42-cadastro-de-concurso-pelo-edital.md)), a retificação
> ganhou um escopo novo: `POSITION`. Cargo que entra, sai, ou muda de vagas,
> cadastro de reserva, salário ou escolaridade agora aparece no diff, com o
> antes e o depois. Era a mudança mais cara que passava invisível: quem escolheu
> um cargo removido perdeu o concurso, e um cargo novo abre uma disputa que
> ninguém estava acompanhando. O casamento é pelo nome normalizado — edital que
> reescreve o nome em maiúsculas não vira cargo novo.

> **Nota (out/2026) — a comparação de assuntos ganhou âncora.** A comparação
> casa assunto por `topic_id` quando ele existe, e por texto quando não. Até
> agora ele **nunca** era escrito: o cadastro pelo edital passou a escrevê-lo
> ao cadastrar o conteúdo programático, então a partir de editais analisados
> por esse caminho a comparação deixa de depender do texto — edital que
> reescreve "1.1 Crase" como "Crase" não vira mais assunto novo.

> **Lacuna conhecida (out/2026).** O concurso passou a ter cronograma próprio
> (ver [cadastro pelo edital](42-cadastro-de-concurso-pelo-edital.md)), e cada
> data registra de qual edital veio — foi desenhado para que uma retificação
> possa substituí-la. Mas **aplicar** a retificação ao cronograma ainda não
> existe: o diff diz que a prova foi adiada e o cronograma continua com a data
> antiga. Está escrito aqui para não ser descoberto por um candidato.
