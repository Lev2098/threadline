# Розгортання на Railway

[← README](../../README.md) · [Русский](../ru/railway.md) · [Варіант із VDS](deployment.md)

Жива версія: **https://threadline-production-788a4574.up.railway.app**

Railway не запускає `docker-compose.yml` цілком: кожен контейнер — окремий сервіс, а зв'язок між ними йде приватною мережею `*.railway.internal`. Образи й код ті самі, що й у compose. Відмінності задаються лише змінними оточення.

## Сервіси

| Сервіс | Джерело | Запуск | Особливості |
|---|---|---|---|
| `threadline` (edge) | `frontend/Dockerfile` | nginx | Єдиний публічний домен, порт 80. TLS термінує Railway |
| `backend` | `backend/Dockerfile` | `docker/entrypoint.sh web` | Pre-deploy: `docker/entrypoint.sh migrate`. Том `/app/media` |
| `realtime` | `backend/Dockerfile` | `docker/entrypoint.sh realtime` | WebSocket (uvicorn) |
| `worker` | `backend/Dockerfile` | `docker/entrypoint.sh worker` | Celery |
| `Postgres`, `Redis` | шаблони Railway | — | Томи з шаблону |
| `rabbitmq` | `rabbitmq:4.1-management-alpine` | — | `RABBITMQ_DEFAULT_USER/PASS` |
| `elasticsearch` | `elasticsearch:8.19.3` | — | `ES_SETTING_DISCOVERY_TYPE=single-node`, `ES_SETTING_XPACK_SECURITY_ENABLED=false`, `ES_JAVA_OPTS=-Xms512m -Xmx512m` |

У сервісів `backend`, `realtime`, `worker` у налаштуваннях вказано Root Directory `backend`, у `threadline` — `frontend`.

## Що відрізняється від docker compose

| Питання | У compose | На Railway |
|---|---|---|
| Медіафайли | Спільний том `backend` ↔ nginx | Томи між сервісами не діляться. nginx шукає файл локально, а якщо його немає — проксіює в Django (`SERVE_MEDIA=true`). Заголовки безпеки для медіа додає nginx в обох випадках |
| Upstream'и nginx | `backend:8000`, `realtime:8000` | `BACKEND_UPSTREAM=backend.railway.internal:8000`, `REALTIME_UPSTREAM=realtime.railway.internal:8000` |
| DNS для nginx | `127.0.0.11` | Береться з `/etc/resolv.conf` контейнера (`NGINX_ENTRYPOINT_LOCAL_RESOLVERS=1`, за замовчуванням в образі) |
| IP клієнта | `X-Forwarded-For` від Caddy | `REAL_IP_HEADER=X-Real-IP`, `TRUSTED_PROXIES=0.0.0.0/0`: nginx доступний лише через проксі Railway |
| Міграції | Окремий контейнер `migrate` | Pre-deploy команда `backend` |
| Статика | — | `collectstatic` виконується під час збирання образу |
| Том `/app/media` | Належить користувачу `app` | Railway монтує том від root, тому `RAILWAY_RUN_UID=0` у `backend` |
| Індекс Elasticsearch | На томі | Без тому: якщо індекс створено заново, `migrate` заповнює його з БД (`search_reindex --fill-if-created`) |

## Змінні

`backend` (у `realtime` і `worker` ті самі, секрети — посиланнями `${{backend.DJANGO_SECRET_KEY}}`, `${{backend.JWT_SECRET}}`):

```
DJANGO_DEBUG=false
DJANGO_SECRET_KEY=<випадковий рядок>
JWT_SECRET=<випадковий рядок>
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
# лише backend:
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

## Деплой і демо-дані

```bash
railway link                                   # обрати проект
railway up -s backend -d                       # так само realtime, worker, threadline
railway ssh -s backend -- python manage.py seed_demo --reset --yes
```

Якщо сервіси підключено до GitHub-репозиторію, кожен push у відстежувану гілку перезбирає їх автоматично.
