#!/bin/sh
# One image, several roles: keeps web, worker and migrations on identical code.
set -eu

case "${1:-web}" in
  web)
    # HTTP API: sync Django under WSGI with a thread pool per process. Running
    # sync views under ASGI costs a thread hop per request and per sync
    # middleware; the load test measured that overhead (docs/*/scaling.md).
    # BIND_HOST: "0.0.0.0" by default; "[::]" for an IPv6 private network (e.g.
    # a legacy Railway environment). gunicorn's "[::]" is dual-stack, uvicorn's
    # (realtime below) is IPv6-only, so set it there only if peers use IPv6.
    exec gunicorn config.wsgi:application \
      --bind "${BIND_HOST:-0.0.0.0}:8000" \
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
      --host "$(echo "${BIND_HOST:-0.0.0.0}" | tr -d '[]')" --port 8000 \
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
    # A fresh (e.g. ephemeral) search index is refilled from the database.
    python manage.py search_reindex --fill-if-created
    ;;
  test)
    shift
    exec pytest -p no:cacheprovider "$@"
    ;;
  *)
    exec "$@"
    ;;
esac
