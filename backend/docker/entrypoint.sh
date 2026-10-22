#!/bin/sh
# One image, several roles: keeps web, worker and migrations on identical code.
set -eu

case "${1:-web}" in
  web)
    # uvicorn's own process manager; workers are stateless, scale with WEB_CONCURRENCY or replicas.
    exec uvicorn config.asgi:application \
      --host 0.0.0.0 --port 8000 \
      --workers "${WEB_CONCURRENCY:-2}" \
      --proxy-headers --forwarded-allow-ips="*" \
      --timeout-graceful-shutdown 20 \
      --no-server-header
    ;;
  worker)
    exec celery -A config worker --loglevel=INFO --concurrency="${WORKER_CONCURRENCY:-4}" -Q comments
    ;;
  migrate)
    python manage.py migrate --noinput
    python manage.py collectstatic --noinput --verbosity 0
    python manage.py search_reindex --ensure-only
    ;;
  test)
    shift
    exec pytest "$@"
    ;;
  *)
    exec "$@"
    ;;
esac
