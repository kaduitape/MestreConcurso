# Frontend — Game of Concursos

SPA em React + TypeScript + Vite, com design system próprio em Tailwind CSS 4.

## Desenvolvimento

```bash
npm install
cp ../.env.example ../.env        # VITE_API_URL aponta para a API
npm run dev                       # http://localhost:5173
```

## Qualidade

```bash
npm run typecheck
npm run lint
npm run test -- --run
npm run build
```

## Organização

- `src/components/ui` — primitivos do design system (padrão shadcn/ui sobre Radix).
- `src/components/layout` — casca da aplicação (sidebar, topbar, tema).
- `src/features/*` — telas por domínio.
- `src/lib/api` — cliente HTTP com renovação automática de token e tipos da API.
- `src/providers` — tema e autenticação.

Tokens de cor, raio e sombra vivem em `src/styles/globals.css`. Componentes usam
apenas tokens semânticos (`bg-surface`, `text-muted`, `bg-primary`…), nunca cores soltas —
é isso que mantém claro/escuro consistentes e as cores das disciplinas estáveis.
