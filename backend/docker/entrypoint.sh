#!/usr/bin/env sh
# Entrypoint único para API, workers e beat.
set -e

wait_for() {
  host="$1"; port="$2"; label="$3"; attempts=0
  until python -c "import socket,sys; s=socket.socket(); s.settimeout(2); s.connect(('$host', $port))" 2>/dev/null; do
    attempts=$((attempts + 1))
    if [ "$attempts" -ge 60 ]; then
      echo "[entrypoint] $label indisponível em $host:$port após 60 tentativas" >&2
      exit 1
    fi
    echo "[entrypoint] aguardando $label ($host:$port)…"
    sleep 2
  done
}

MYSQL_HOST="${MYSQL_HOST:-mysql}"
MYSQL_PORT="${MYSQL_PORT:-3306}"
wait_for "$MYSQL_HOST" "$MYSQL_PORT" "MySQL"

case "$1" in
  api|api-reload)
    echo "[entrypoint] aplicando migrations"
    alembic upgrade head
    if [ "${RUN_SEED:-true}" = "true" ]; then
      echo "[entrypoint] executando seed idempotente (papéis, permissões e admin inicial)"
      python -m app.cli seed
    fi
    ;;
esac

case "$1" in
  api)
    exec gunicorn app.main:app \
      --worker-class uvicorn.workers.UvicornWorker \
      --workers "${WEB_CONCURRENCY:-4}" \
      --bind 0.0.0.0:8000 \
      --timeout 60 \
      --graceful-timeout 30 \
      --access-logfile - \
      --error-logfile -
    ;;
  api-reload)
    exec uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
    ;;
  worker)
    shift
    exec celery -A app.workers.celery_app.celery_app worker \
      --loglevel="${CELERY_LOG_LEVEL:-info}" \
      --queues="${CELERY_QUEUES:-default,notifications}" \
      --concurrency="${CELERY_CONCURRENCY:-4}" "$@"
    ;;
  beat)
    exec celery -A app.workers.celery_app.celery_app beat --loglevel="${CELERY_LOG_LEVEL:-info}"
    ;;
  *)
    exec "$@"
    ;;
esac
