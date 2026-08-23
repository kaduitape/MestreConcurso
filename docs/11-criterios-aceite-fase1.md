# 14. Critérios de Aceite da Fase 1

## Infraestrutura
1. `cp .env.example .env && docker compose up -d` sobe mysql, redis, api, worker, beat, frontend e mailhog sem intervenção manual.
2. `GET /health` responde 200; `GET /ready` verifica MySQL e Redis e responde 503 quando algum estiver fora.
3. `/docs` (Swagger) e `/openapi.json` refletem todos os endpoints com schemas tipados.
4. Migrations aplicadas automaticamente; `alembic downgrade base` e `upgrade head` funcionam.

## Autenticação e contas
5. Registro cria usuário `PENDING`, dispara e-mail de verificação (visível no Mailhog) e **não** autentica antes da confirmação.
6. Verificação de e-mail é single-use e expira; token inválido retorna erro claro.
7. Login com credenciais válidas devolve `access` (15 min) e `refresh` (30 dias) com sessão registrada (dispositivo, IP, user-agent).
8. Login errado incrementa contador e bloqueia temporariamente após N tentativas (configurável).
9. `POST /auth/refresh` rotaciona o refresh; reuso de token já rotacionado revoga toda a família e registra auditoria.
10. `POST /auth/logout` encerra a sessão atual; `POST /auth/logout-all` encerra todas; `DELETE /users/me/sessions/{id}` encerra uma específica.
11. Recuperação de senha: token expira, é single-use, invalida todas as sessões ao ser usado.
12. Troca de senha exige senha atual e revoga as demais sessões.
13. Senhas armazenadas com Argon2id; nenhum hash legível ou reversível; política de força validada no back e no front.

## RBAC e admin
14. Papéis `admin`, `staff`, `student` são criados por seed idempotente com permissões `resource:action`.
15. Endpoints administrativos negam acesso (403) a usuário sem permissão e registram a tentativa em `audit_logs`.
16. Painel `/admin` lista usuários com paginação/busca no servidor, permite ativar/suspender, atribuir papéis e exibe a auditoria.

## Qualidade transversal
17. Rate limiting ativo nas rotas de auth (por IP e por identificador), com `Retry-After` e headers `X-RateLimit-*`.
18. Toda resposta traz `X-Request-ID`; todo log é JSON com `request_id` e `user_id` quando houver.
19. Erros seguem envelope único `{error: {code, message, details, request_id}}`; nenhum stack trace vaza ao cliente.
20. Cabeçalhos de segurança presentes (CSP, HSTS em prod, `X-Content-Type-Options`, `Referrer-Policy`, `X-Frame-Options`) e CORS restrito por env.
21. LGPD: exportação dos dados da conta (JSON) e exclusão de conta (anonimização + revogação de sessões) funcionando, com log de consentimento no registro.
22. `pytest` verde cobrindo hashing, política de senha, JWT, rotação de refresh, RBAC, rate limit e o fluxo completo de auth; `ruff` e `mypy` sem erro no pacote `app`.

## Frontend
23. Tema claro/escuro persistente, tokens do design system centralizados, sem cor "solta" em componente.
24. Fluxo completo utilizável: registrar → verificar → login → dashboard → perfil → dispositivos → logout.
25. Sessão expirada dispara refresh transparente; falha de refresh leva ao login preservando a rota de destino.
26. Command palette (Ctrl/⌘+K) navega de verdade entre as telas existentes — nenhum item decorativo.
27. Estados de carregamento (skeleton), vazio e erro implementados em todas as telas da fase; nenhum dado falso ou botão sem função.
28. Build de produção (`npm run build`) sem erro de TypeScript e sem `any` implícito.
