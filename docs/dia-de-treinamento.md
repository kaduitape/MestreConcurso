# Dia de Treinamento — Estúdio e narração

O Estúdio produz aulas em **cenas editáveis**, não em vídeo fechado: o roteiro é
gerado por IA, revisado por uma pessoa e publicado como timeline. Narração,
avatar e efeitos são camadas dessa mesma timeline — nunca um MP4 obrigatório.

# Narração das aulas

> **Regra que governa esta parte:** a IA escolhe **entonação, nunca informação**.
> O texto falado é exatamente o que o roteiro aprovado por uma pessoa trazia; o
> que se acrescenta é como ler — e isso é forma, não conteúdo.

A voz do navegador lê um bloco de texto e nada mais, por isso soa plana. Aqui o
roteiro é quebrado em **trechos** e cada trecho leva uma **direção de cena**.

## Direção de cena
1. A direção é montada a partir dos campos que o roteiro **já declarava**: o tipo da cena (`intro`, `explanation`, `example`, `question`, `summary`, `closing`), a emoção do personagem (`character.emotion`) e os termos em `emphasis`.
2. Os termos em destaque viram pedido de ênfase e pausa — são os que o roteiro marcou para fixar, e não um palpite do código sobre o que importa.
3. O primeiro e o último trecho de cada cena são lidos diferente: um entra com presença, o outro fecha a frase em vez de deixá-la no ar.
4. A moldura é medieval **no porte, não na fantasia**: um mestre de armas que ensina português. A direção pede dicção clara e proíbe arcaísmo forçado — o conteúdo é técnico e precisa ser entendido de primeira.

## Trechos
5. O texto é quebrado por frase. Frase curta demais gruda na seguinte: um "Pois bem." sozinho viraria um arquivo cuja pausa de carregamento dura mais que a palavra.
6. Frase acima de 180 caracteres é partida na vírgula mais próxima do meio. Além disso o destaque fica parado tempo demais e a leitura volta a soar como um bloco.
7. **Nada do texto se perde na quebra**, e cada trecho sabe sua posição dentro da cena — é o que permite acender exatamente a frase que está tocando, em vez de estimar onde a voz deveria estar.

## O token é pago uma vez
8. Cada trecho é identificado por um checksum de **texto + direção + voz + modelo**. Reabrir a aula não gera nada.
9. Reescrever uma vírgula gera **só o trecho que mudou**; o resto da aula continua valendo.
10. Trocar a voz não apaga o áudio existente: ele continua identificado pela voz antiga, e só a próxima geração produz os trechos na voz nova.
11. "Refazer tudo" apaga os arquivos antes de regerar — áudio órfão encheria o armazenamento sem ninguém referenciá-lo.

## A aula funciona sem narração
12. Sem provedor configurado, sem modelo de voz, ou com a geração falhando, **a aula continua a mesma**: o player cai para a voz do navegador.
13. E **diz qual voz está no ar**. A diferença é audível, e fingir que são a mesma coisa enganaria quem configura a plataforma.
14. Uma cena só usa a voz gerada quando **todos** os seus trechos têm áudio. Metade gerada e metade sintetizada trocaria de voz no meio da cena.
15. Falha ao carregar um trecho não trava a cena: ela segue para o próximo.
16. O painel administrativo mostra **o motivo** quando não dá para gerar, em vez de esconder o botão — o que falta é configuração, e quem administra precisa saber disso.

## Configuração
17. A narração é uma funcionalidade de IA como as outras: provedor e modelo são escolhidos no painel (`training.narration`), e o modelo precisa ser de voz.
18. A voz padrão vive nas opções da funcionalidade; **cada aula pode ter a sua**, porque personagens diferentes merecem vozes diferentes.
19. Voz que não existe no provedor configurado é recusada. Sem provedor, a lista de vozes vem vazia — melhor nenhuma opção do que um menu de escolhas que não funcionam.
20. O áudio é servido por rota pública, como a arte da batalha: um `<audio>` não carrega o token da aplicação.
21. O adaptador da OpenAI ganhou a API de fala, e o da AISA a herda — é o mesmo contrato HTTP. Provedor que não fala **recusa com esse nome** em vez de devolver silêncio.

## Qualidade
22. 25 testes de domínio e 11 de integração. Entre eles: que o texto falado é o do roteiro, que a direção de cena chega ao provedor, que gerar duas vezes não chama a API de novo, e que reescrever uma cena custa só aquela cena.
23. Migração `training_narrations` (+ `narration_voice` na aula e `options` no vínculo de IA) sobe e desce limpa.
