# syntax=docker/dockerfile:1.7
# ---------------------------------------------------------------------------
# Dependências
# ---------------------------------------------------------------------------
FROM node:22-alpine AS deps
WORKDIR /app
COPY package.json package-lock.json* ./
RUN npm ci || npm install

# ---------------------------------------------------------------------------
# Dev — Vite com hot reload (usado pelo docker compose de desenvolvimento)
# ---------------------------------------------------------------------------
FROM node:22-alpine AS dev
WORKDIR /app
ENV NODE_ENV=development
COPY --from=deps /app/node_modules ./node_modules
COPY . .
EXPOSE 5173
CMD ["npm", "run", "dev"]

# ---------------------------------------------------------------------------
# Build de produção
# ---------------------------------------------------------------------------
FROM node:22-alpine AS build
WORKDIR /app
ARG VITE_API_URL=http://localhost:8000
ENV VITE_API_URL=$VITE_API_URL
COPY --from=deps /app/node_modules ./node_modules
COPY . .
RUN npm run build

# ---------------------------------------------------------------------------
# Web — nginx servindo o SPA
# ---------------------------------------------------------------------------
FROM nginx:alpine AS web
COPY nginx.conf /etc/nginx/conf.d/default.conf
COPY --from=build /app/dist /usr/share/nginx/html
EXPOSE 80
HEALTHCHECK --interval=30s --timeout=5s --retries=3 \
    CMD wget -qO- http://localhost/ >/dev/null || exit 1
