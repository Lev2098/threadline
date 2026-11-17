# Развёртывание на Railway

[← README](../../README.ru.md) · [Українська](../uk/railway.md) · [Вариант с VDS](deployment.md)

Живая версия: **https://threadline-production-788a4574.up.railway.app**

Railway не запускает `docker-compose.yml` целиком: каждый контейнер — отдельный сервис, а связь между ними идёт по приватной сети `*.railway.internal`. Образы и код те же, что и в compose. Различия задаются только переменными окружения.

## Сервисы

| Сервис | Источник | Запуск | Особенности |
|---|---|---|---|
| `threadline` (edge) | `frontend/Dockerfile` | nginx | Единственный публичный домен, порт 80. TLS терминирует Railway |
| `backend` | `backend/Dockerfile` | `docker/entrypoint.sh web` | Pre-deploy: `docker/entrypoint.sh migrate`. Том `/app/media` |
| `realtime` | `backend/Dockerfile` | `docker/entrypoint.sh realtime` | WebSocket (uvicorn) |
| `worker` | `backend/Dockerfile` | `docker/entrypoint.sh worker` | Celery |
| `Postgres`, `Redis` | шаблоны Railway | — | Тома из шаблона |
| `rabbitmq` | `rabbitmq:4.1-management-alpine` | — | `RABBITMQ_DEFAULT_USER/PASS` |
| `elasticsearch` | `elasticsearch:8.19.3` | — | `ES_SETTING_DISCOVERY_TYPE=single-node`, `ES_SETTING_XPACK_SECURITY_ENABLED=false`, `ES_JAVA_OPTS=-Xms512m -Xmx512m` |

У сервисов `backend`, `realtime`, `worker` в настройках указан Root Directory `backend`, у `threadline` — `frontend`.

## Что отличается от docker compose

| Вопрос | В compose | На Railway |
|---|---|---|
| Медиафайлы | Общий том `backend` ↔ nginx | Тома между сервисами не делятся. nginx ищет файл локально, а если его нет — проксирует в Django (`SERVE_MEDIA=true`). Заголовки безопасности для медиа добавляет nginx в обоих случаях |
| Upstream'ы nginx | `backend:8000`, `realtime:8000` | `BACKEND_UPSTREAM=backend.railway.internal:8000`, `REALTIME_UPSTREAM=realtime.railway.internal:8000` |
| DNS для nginx | `127.0.0.11` | Берётся из `/etc/resolv.conf` контейнера (`NGINX_ENTRYPOINT_LOCAL_RESOLVERS=1`, по умолчанию в образе) |
| IP клиента | `X-Forwarded-For` от Caddy | `REAL_IP_HEADER=X-Real-IP`, `TRUSTED_PROXIES=0.0.0.0/0`: nginx доступен только через прокси Railway |
| Миграции | Отдельный контейнер `migrate` | Pre-deploy команда `backend` |
| Статика | — | `collectstatic` выполняется при сборке образа |
| Том `/app/media` | Принадлежит пользователю `app` | Railway монтирует том от root, поэтому `RAILWAY_RUN_UID=0` у `backend` |
| Индекс Elasticsearch | На томе | Без тома: если индекс создан заново, `migrate` заполняет его из БД (`search_reindex --fill-if-created`) |

## Переменные

`backend` (у `realtime` и `worker` те же, секреты — ссылками `${{backend.DJANGO_SECRET_KEY}}`, `${{backend.JWT_SECRET}}`):

```
DJANGO_DEBUG=false
DJANGO_SECRET_KEY=<случайная строка>
JWT_SECRET=<случайная строка>
DJANGO_ALLOWED_HOSTS=${{threadline.RAILWAY_PUBLIC_DOMAIN}}
DJANGO_CSRF_TRUSTED_ORIGINS=https://${{threadline.RAILWAY_PUBLIC_DOMAIN}}
SITE_URL=https://${{threadline.RAILWAY_PUBLIC_DOMAIN}}
BEHIND_TLS_PROXY=true
SECURE_COOKIES=true
TRUST_PROXY_HEADERS=true
POSTGRES_HOST=${{Postgres.PGHOST}}
POSTGRES_PORT=${{Postgres.PGPORT}}
POSTGRES_DB=${{Postgres.PGDATABASE}}
POSTGRES_USER=${{Postgres.PGUSER}}
POSTGRES_PASSWORD=${{Postgres.PGPASSWORD}}
REDIS_URL=${{Redis.REDIS_URL}}
CELERY_BROKER_URL=amqp://${{rabbitmq.RABBITMQ_DEFAULT_USER}}:${{rabbitmq.RABBITMQ_DEFAULT_PASS}}@rabbitmq.railway.internal:5672//
ELASTICSEARCH_URL=http://elasticsearch.railway.internal:9200
SPA_SHELL_URL=http://threadline.railway.internal/index.html
PORT=8000
WEB_CONCURRENCY=2
WEB_THREADS=8
WORKER_CONCURRENCY=2
# только backend:
SERVE_MEDIA=true
RAILWAY_RUN_UID=0
```

`threadline`:

```
BACKEND_UPSTREAM=backend.railway.internal:8000
REALTIME_UPSTREAM=realtime.railway.internal:8000
TRUSTED_PROXIES=0.0.0.0/0
REAL_IP_HEADER=X-Real-IP
PORT=80
```

## Деплой и демо-данные

```bash
railway link                                   # выбрать проект
railway up -s backend -d                       # так же realtime, worker, threadline
railway ssh -s backend -- python manage.py seed_demo --reset --yes
```

Если сервисы подключены к GitHub-репозиторию, каждый push в отслеживаемую ветку пересобирает их автоматически.
