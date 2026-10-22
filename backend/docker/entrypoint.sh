#!/bin/sh
# One image, several roles: keeps web, worker and migrations on identical code.
set -eu

case "${1:-web}" in
  web)
    # HTTP API: sync Django under WSGI with a thread pool per process. Running
    # sync views under ASGI costs a thread hop per request and per sync
    # middleware; the load test measured that overhead (docs/*/scaling.md).
    exec gunicorn config.wsgi:application \
      --bind 0.0.0.0:8000 \
      --worker-class gthread \
      --workers "${WEB_CONCURRENCY:-2}" \
      --threads "${WEB_THREADS:-8}" \
      --max-requests 50000 --max-requests-jitter 5000 \
      --keep-alive 75 \
      --graceful-timeout 20 --timeout 30 \
      --forwarded-allow-ips "*"
    ;;
  realtime)
    # WebSockets only: ASGI (Channels) on uvicorn.
    exec uvicorn config.asgi:application \
      --host 0.0.0.0 --port 8000 \
      --workers "${REALTIME_CONCURRENCY:-1}" \
      --proxy-headers --forwarded-allow-ips="*" \
      --timeout-graceful-shutdown 20 \
      --no-access-log --no-server-header
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
    exec pytest -p no:cacheprovider "$@"
    ;;
  *)
    exec "$@"
    ;;
esac
