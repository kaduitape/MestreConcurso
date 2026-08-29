# Deploy automático na VPS

Todo `push` na branch `master` executa o workflow **Deploy VPS**. Ele atualiza a
cópia do repositório na VPS, reconstrói os containers de produção, aplica as
migrations e só termina com sucesso quando a API responde ao health check.

## Preparar a VPS (uma vez)

Na VPS, instale Docker Engine com o plugin Compose, clone este repositório na
pasta definitiva e crie o arquivo de ambiente fora do Git:

```bash
git clone https://github.com/kaduitape/MestreConcurso.git /opt/mestre-concurso
cd /opt/mestre-concurso
cp .env.example .env
chmod 600 .env
```

No `.env`, defina segredos fortes para `SECRET_KEY`, `MYSQL_PASSWORD` e
`MYSQL_ROOT_PASSWORD`, além de `VITE_API_URL` com a URL pública da API. Em
produção, use `ENVIRONMENT=production`, `DEBUG=false`, CORS e hosts permitidos
com o domínio real. O usuário SSH de deploy deve executar `docker compose` sem
`sudo`.

Faça o primeiro deploy manualmente na VPS:

```bash
docker compose --env-file .env -f docker-compose.yml -f docker-compose.production.yml up -d --build
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
