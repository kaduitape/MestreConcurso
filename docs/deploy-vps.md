# Deploy automático na VPS

Todo `push` na branch `master` executa o workflow **Deploy VPS**. Ele atualiza a
cópia do repositório na VPS, reconstrói os containers de produção, aplica as
migrations e só termina com sucesso quando a API responde ao health check.

## O deploy testa o caminho do usuário, não só a API

O passo final não pergunta "a API está viva?" — pergunta "o navegador consegue
falar com ela?". São duas checagens, nesta ordem:

1. `curl` dentro do contêiner da API. Prova que as migrations rodaram e o app
   subiu.
2. `wget` dentro do contêiner do frontend, batendo em `/health`. Esse caminho
   atravessa o nginx, então pega também proxy apontando para o lugar errado.
   O `Host` da requisição sai do `ALLOWED_HOSTS` do `.env`: a API roda com
   `TrustedHostMiddleware` e responde **400 `Invalid host header`** para
   qualquer outro. Usar o host real é o que faz a checagem exercitar o mesmo
   caminho do navegador, e não um atalho que produção não usa.

A segunda existe porque a primeira sozinha já deixou passar uma produção
quebrada: o deploy ficou verde enquanto **todo `/api/` respondia 502**.

### A armadilha do stdin

Todo `compose exec` no script do deploy fecha a entrada com `</dev/null`, e isso
não é adorno. O script inteiro chega no servidor **pelo stdin** do `bash -s`.
O `compose exec` conecta o stdin ao processo remoto mesmo com `-T`; quando ele
drena o que sobrou do heredoc, **o resto do script desaparece** e o passo
termina com sucesso sem ter executado checagem nenhuma.

É uma corrida, então falha de forma intermitente: um deploy passou por sorte e o
seguinte morreu logo depois do `up -d` — verde, e sem ter verificado nada.

### Por que o proxy quebrava

O `proxy_pass` do nginx usa uma **variável** (`set $api_upstream ...`) e o
`resolver` do Docker (`127.0.0.11`), em vez do host escrito direto. Com o host
literal, o nginx resolve o nome **uma única vez, ao subir**, e guarda o IP para
sempre.

Quando um deploy recria só o contêiner da API — porque a imagem do frontend não
mudou —, a API volta com outro IP na rede do Docker e o nginx segue falando com
o endereço morto. O resultado é 502 com corpo HTML, que o frontend não consegue
ler como erro e exibe como "não foi possível concluir a operação".

O healthcheck do próprio contêiner do frontend não cobre isso de propósito: ele
bate em `/`, que é arquivo estático. Marcar o frontend como insalubre toda vez
que a API reinicia causaria mais problema do que resolve — a checagem
ponta a ponta é trabalho do deploy.

## As migrations rodam em um lugar só

O `alembic upgrade head` é disparado **apenas pelo entrypoint do contêiner da
API**, antes de o gunicorn subir. O workflow não dispara de novo, e isso é
deliberado:

- `docker compose up -d` retorna quando o contêiner **inicia**, não quando o
  entrypoint termina. Disparar o alembic logo em seguida colocava dois
  processos migrando o mesmo banco ao mesmo tempo.
- Em MySQL o DDL **não tem rollback**. Numa corrida assim, os dois leem a mesma
  versão, um cria a tabela e o outro morre com `1050 ... already exists` — e a
  tabela fica de pé **sem o carimbo de versão**. O banco para num estado que
  nenhuma revisão descreve, e toda subida seguinte repete o mesmo erro.
- Como o `/health` só responde depois das migrations, esperar pelo health check
  é esperar por elas. Se as migrations falharem, o contêiner não sobe, o health
  check estoura em 120s e o passo imprime os últimos 300 logs da API.

Como rede de segurança, `backend/alembic/env.py` pega uma **trava consultiva**
(`GET_LOCK`) no MySQL antes de migrar: se alguém rodar `alembic upgrade head` à
mão durante um deploy, o segundo processo espera em vez de corromper o schema.
A trava vive na sessão — se o processo morrer, o MySQL a solta sozinho.

## Preparar a VPS (uma vez)

Na VPS, instale Docker Engine com o plugin Compose **v2.24 ou superior**, clone
este repositório na pasta definitiva e crie o arquivo de ambiente fora do Git:

```bash
git clone https://github.com/kaduitape/MestreConcurso.git /opt/mestre-concurso
cd /opt/mestre-concurso
cp .env.production.example .env
chmod 600 .env
```

No `.env`, substitua todos os valores `SUBSTITUA`, informe o domínio real em
`FRONTEND_URL`, `BACKEND_URL`, `CORS_ORIGINS` e `ALLOWED_HOSTS`, e mantenha
`ENVIRONMENT=production` e `DEBUG=false`. O usuário SSH de deploy deve executar
`docker compose` sem `sudo`.

A API, MySQL, Redis, Qdrant e MailHog ficam privados na rede Docker. Apenas o
frontend publica a porta `80`; o Nginx encaminha `/api/*` internamente para a
API. Portanto, com o domínio apontando para a VPS, o valor recomendado de
`VITE_API_URL` é `/` (já definido no exemplo). Para HTTPS, coloque um proxy/TLS
na frente da porta 80 ou configure o terminador TLS que você utiliza na VPS.

O backend usa `backend/pyproject.toml` como manifesto de dependências Python;
por isso não existe `requirements.txt`. O frontend usa
`frontend/package.json` e `frontend/package-lock.json`. Os dois Dockerfiles e
seus `.dockerignore` correspondentes já apontam para essas pastas.

Faça o primeiro deploy manualmente na VPS:

```bash
docker compose --env-file .env -f docker-compose.yml -f docker-compose.production.yml up -d --build
```

Confira antes de publicar:

```bash
docker compose --env-file .env -f docker-compose.yml -f docker-compose.production.yml config -q
curl -fsS http://localhost/health
```

## Segredos no GitHub

Em **Settings → Secrets and variables → Actions**, crie estes segredos:

| Segredo | Valor |
| --- | --- |
| `VPS_HOST` | IP ou domínio da VPS |
| `VPS_PORT` | porta SSH, normalmente `22` |
| `VPS_USER` | usuário dedicado ao deploy |
| `VPS_APP_DIR` | caminho do clone, por exemplo `/opt/mestre-concurso` |
| `VPS_SSH_PRIVATE_KEY` | chave privada ED25519 do usuário de deploy |
| `VPS_KNOWN_HOSTS` | linha verificada de `ssh-keyscan -H -p PORTA HOST` |

Cadastre a chave pública correspondente em `~/.ssh/authorized_keys` desse
usuário na VPS. Confirme a fingerprint por um canal confiável antes de salvar
`VPS_KNOWN_HOSTS`; o workflow recusa servidores cuja chave não corresponda.

O deploy falha se encontrar alterações locais na VPS, preservando o `.env` e
evitando que mudanças manuais sejam substituídas silenciosamente.
