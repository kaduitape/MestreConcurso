# Deploy automático na VPS

Todo `push` na branch `master` executa o workflow **Deploy VPS**. Ele atualiza a
cópia do repositório na VPS, reconstrói os containers de produção, aplica as
migrations e só termina com sucesso quando a API responde ao health check.

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
