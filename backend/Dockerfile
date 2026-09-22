# syntax=docker/dockerfile:1.7
# ---------------------------------------------------------------------------
# Base — dependências de sistema mínimas e usuário sem privilégios
# ---------------------------------------------------------------------------
FROM python:3.13-slim AS base

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    PATH="/opt/venv/bin:$PATH"

RUN apt-get update \
    && apt-get install -y --no-install-recommends curl tini \
    # OCR para editais digitalizados (sem camada de texto).
    tesseract-ocr tesseract-ocr-por \
    && rm -rf /var/lib/apt/lists/* \
    && groupadd --gid 1000 app \
    && useradd --uid 1000 --gid app --create-home app

WORKDIR /app

# ---------------------------------------------------------------------------
# Builder — cria o virtualenv com as dependências
# ---------------------------------------------------------------------------
FROM base AS builder

RUN apt-get update \
    && apt-get install -y --no-install-recommends build-essential \
    && rm -rf /var/lib/apt/lists/*

RUN python -m venv /opt/venv
COPY pyproject.toml README.md ./
COPY app/__init__.py app/__init__.py
RUN pip install --upgrade pip && pip install .

# ---------------------------------------------------------------------------
# Runtime — imagem final da API e dos workers
# ---------------------------------------------------------------------------
FROM base AS runtime

COPY --from=builder /opt/venv /opt/venv
COPY --chown=app:app . .
RUN sed -i 's/\r$//' docker/entrypoint.sh \
    && install -m 755 docker/entrypoint.sh /usr/local/bin/mestre-entrypoint \
    # Diretório de uploads criado com dono correto: o volume nomeado herda estas
    # permissões e o processo (uid 1000) consegue gravar.
    && mkdir -p /var/lib/mestre/uploads \
    && chown -R app:app /app /var/lib/mestre

USER app
EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=5s --start-period=40s --retries=3 \
    CMD curl -fsS http://localhost:8000/health || exit 1

ENTRYPOINT ["/usr/bin/tini", "--", "/usr/local/bin/mestre-entrypoint"]
CMD ["api"]

# ---------------------------------------------------------------------------
# Dev — inclui ferramentas de teste e hot reload
# ---------------------------------------------------------------------------
FROM runtime AS dev

USER root
COPY --from=builder /opt/venv /opt/venv
RUN pip install ".[dev]"
USER app
CMD ["api-reload"]
