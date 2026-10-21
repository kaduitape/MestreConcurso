# O carimbo de versão perdido

> Incidente de produção, 20/10/2026. O deploy da Fase 1 ficou **verde** e deixou
> o banco num estado que nenhuma revisão descreve. O deploy seguinte morreu com
> `Duplicate column name 'editorial_status'`.

## O que apareceu

```
(1060, "Duplicate column name 'editorial_status'")
[SQL: ALTER TABLE competitions ADD COLUMN editorial_status VARCHAR(20) NOT NULL DEFAULT 'DRAFT']
```

A coluna é da Fase 1, que já tinha subido. O Alembic estava repetindo uma
migração que já havia rodado — ou seja, **o carimbo de versão não avançou**,
embora o DDL tivesse rodado e o deploy tivesse passado nas duas checagens de
saúde.

## A causa

A trava consultiva que impede dois `alembic upgrade head` no mesmo banco rodava
o `SELECT GET_LOCK(...)` **na mesma conexão** que o Alembic ia usar.

1. O SQLAlchemy 2 abre transação sozinho no primeiro comando da conexão.
2. O Alembic, ao ser configurado, vê uma conexão com transação aberta e conclui
   que a transação é de **outra pessoa** (`_in_external_transaction`).
3. A partir daí, `begin_transaction()` vira um no-op: ele nunca mais confirma
   nada, porque assume que quem abriu a transação vai confirmar.
4. Em MySQL o DDL **se auto-confirma**, e cada DDL confirma também o que estava
   pendente antes dele. Então o schema subiu inteiro — e, de quebra, o carimbo
   de cada migração foi confirmado pelo DDL da migração **seguinte**.
5. O `UPDATE alembic_version` da **última** migração não tem DDL depois dele.
   Ficou pendente e foi descartado quando a conexão fechou.

O defeito entrou no deploy #11, junto com a trava. Ficou invisível até o #15,
que foi o primeiro deploy com migração nova depois dela.

## A reprodução

Antes de consertar, o mecanismo foi reproduzido num MySQL 8.4 de verdade: subir
a cadeia inteira deixava o schema no topo e o `alembic_version` em
`35cf5e2fb21f` — a penúltima revisão. Depois do conserto, `68ce8082ab6c`, que é
a cabeça.

O estado exato da produção também foi montado à mão (schema da Fase 1 aplicado,
carimbo em `fea78a95bd3e`) e reproduziu o erro do deploy #16 palavra por
palavra, antes de qualquer alteração.

## O conserto

1. **A trava mora numa conexão própria.** A conexão das migrações chega limpa
   ao Alembic, por construção.
2. **Conexão suja é recusada aos berros.** `ensure_clean_for_alembic` derruba a
   subida com a explicação escrita. Carimbo perdido em silêncio não quebra o
   deploy que o perdeu — quebra o seguinte, e aí a causa já está longe.
3. **A migração da Fase 1 ficou re-executável**, no mesmo idioma já usado para
   a narração: pula o que já existe, para o banco machucado alcançar a versão
   certa. O preenchimento do estado editorial só toca linhas que ninguém
   decidiu ainda.
4. A trava continua fazendo o trabalho dela: dois `alembic upgrade head`
   simultâneos foram testados no MySQL — um aplicou as 26 migrações, o outro
   esperou e não achou nada para fazer, os dois saíram com código 0 e sem um
   único conflito de DDL.

## Defeito de rollback encontrado no caminho

Descer as migrações da Fase 2 no MySQL falhava:

```
(1553, "Cannot drop index 'ix_agent_runs_competition_id': needed in a foreign key constraint")
```

O SQLite dos testes não reclama, então isso nunca apareceu na suíte. A ordem da
descida depende do dialeto — onde a tabela é recriada o índice precisa sair
antes, onde ela é alterada no lugar o índice precisa sair depois — e agora as
três revisões novas sobem, descem e sobem de novo num MySQL de verdade.

Fica registrado o que **não** foi mexido: migrações antigas têm o mesmo risco na
descida até `base` no MySQL. Produção nunca desce até `base`, e alargar a
mudança para a história inteira não se justificava neste conserto.

## O que a suíte passou a cobrar

- Conexão com transação aberta é recusada, com a mensagem dizendo o que
  aconteceria.
- `upgrade head` termina com o carimbo **na cabeça** — não na revisão anterior.
- O banco com o schema novo e o carimbo antigo consegue se endireitar, sem
  duplicar índice nem chave estrangeira pelo caminho.

## Versões fixadas depois do incidente

O defeito não estava só no nosso código: ele dependia de um detalhe de
comportamento do **par** SQLAlchemy + Alembic — quando o Alembic considera a
transação "externa" e, a partir daí, não confirma mais nada. Esse detalhe pode
mudar entre versões.

As duas bibliotecas estavam declaradas em faixa aberta (`>=`), então cada build
do contêiner trazia o que fosse mais novo no dia. Agora estão **fixas**:

```toml
"sqlalchemy[asyncio]==2.1.5",
"alembic==1.20.0",
```

Subir qualquer uma passa a ser uma alteração explícita, com a suíte rodando
antes — que é exatamente a conferência que faltava.

Fica registrado o que **não** foi feito: as outras dependências continuam em
faixa aberta. Um arquivo de bloqueio para o backend inteiro resolveria o
problema por completo, e continua sendo a recomendação; esta mudança fecha o
caso conhecido, não a categoria.
