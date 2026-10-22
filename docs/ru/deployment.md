# Развёртывание шаг за шагом

[← README](../../README.ru.md) · [Українська](../uk/deployment.md)

Инструкция рассчитана на чистый VDS с **Ubuntu 22.04/24.04**. На другом Linux с Docker шаги те же.

## 0. Что понадобится

| Ресурс | Минимум | Рекомендуется |
|---|---|---|
| CPU | 2 vCPU | 4 vCPU |
| RAM | 4 ГБ (Elasticsearch берёт ~1 ГБ) | 8 ГБ |
| Диск | 20 ГБ SSD | 40 ГБ SSD |
| Домен | необязательно (можно по IP) | да, для HTTPS |

## 1. DNS (если есть домен)

В панели регистратора создайте **A-запись** `comments.example.com → <IP сервера>`. Проверка:

```bash
dig +short comments.example.com     # должен вернуть IP сервера
```

## 2. Подготовка сервера

```bash
ssh root@<IP>

# обновление системы
apt update && apt -y upgrade

# отдельный пользователь вместо root
adduser deploy
usermod -aG sudo deploy

# файрвол: SSH, HTTP, HTTPS
ufw allow OpenSSH
ufw allow 80/tcp
ufw allow 443/tcp
ufw allow 443/udp
ufw --force enable
```

## 3. Установка Docker

```bash
curl -fsSL https://get.docker.com | sh
usermod -aG docker deploy
su - deploy                          # перелогиниться, чтобы группа применилась
docker --version && docker compose version
```

## 4. Код

```bash
git clone https://github.com/Lev2098/threadline.git threadline
cd threadline
```

## 5. Настройка `.env`

```bash
cp .env.example .env

# сгенерировать секреты
sed -i "s|^DJANGO_SECRET_KEY=.*|DJANGO_SECRET_KEY=$(openssl rand -hex 32)|" .env
sed -i "s|^JWT_SECRET=.*|JWT_SECRET=$(openssl rand -hex 32)|" .env
sed -i "s|^POSTGRES_PASSWORD=.*|POSTGRES_PASSWORD=$(openssl rand -hex 16)|" .env
sed -i "s|^RABBITMQ_PASSWORD=.*|RABBITMQ_PASSWORD=$(openssl rand -hex 16)|" .env
nano .env
```

Отредактируйте в `.env` (и раскомментируйте эти строки):

```dotenv
DJANGO_ALLOWED_HOSTS=comments.example.com
DJANGO_CSRF_TRUSTED_ORIGINS=https://comments.example.com
DOMAIN=comments.example.com
SITE_URL=https://comments.example.com
BEHIND_TLS_PROXY=true
SECURE_COOKIES=true
COMPOSE_FILE=docker-compose.yml:docker-compose.prod.yml
```

`COMPOSE_FILE` делает продакшн-оверлей (Caddy + HTTPS, закрытые порты приложения) частью **каждой** команды `docker compose …` на этом сервере. Без него `docker compose up -d` при обновлении или масштабировании тихо вернул бы стек в локальный режим с открытым портом 8080.

> **Без домена** (только IP): `DJANGO_ALLOWED_HOSTS=<IP>`, `DJANGO_CSRF_TRUSTED_ORIGINS=http://<IP>:8080`, строки `DOMAIN`, `BEHIND_TLS_PROXY`, `SECURE_COOKIES` и `COMPOSE_FILE` не добавляйте. Сайт будет на `http://<IP>:8080`.

> **Docker и ufw.** Порты, которые публикует Docker, обходят правила ufw. Поэтому продакшн-оверлей не публикует ничего, кроме 80/443 (Caddy), а RabbitMQ UI слушает только `127.0.0.1` (доступ через `ssh -L 15672:localhost:15672`).

> **Подсеть.** Стек использует сеть `172.28.0.0/24` (Caddy имеет фиксированный адрес `172.28.0.250`, только ему nginx доверяет `X-Forwarded-For`). Если на сервере эта подсеть занята, задайте в `.env` `COMPOSE_SUBNET` и `CADDY_IP`.

## 6. Запуск

```bash
docker compose up -d --build
```

Первый запуск занимает 3–5 минут (сборка образов). Сервис `migrate` сам применит миграции, соберёт статику и создаст индекс Elasticsearch, а `backend` стартует только после этого.

## 7. Проверка

```bash
docker compose ps -a                 # все сервисы running (healthy), migrate: exited (0)
curl -s https://comments.example.com/readyz     # {"status": "ready"}
```

Откройте `https://comments.example.com` и оставьте комментарий. Откройте сайт во второй вкладке: новый комментарий появится там без перезагрузки.

## 8. Администратор и демо-данные (по желанию)

```bash
docker compose exec backend python manage.py createsuperuser
docker compose exec backend python manage.py seed_comments --count 5000
docker compose exec backend python manage.py search_reindex
```

## 9. Обновление

```bash
cd ~/threadline
git pull
docker compose up -d --build        # COMPOSE_FILE из .env добавляет продакшн-оверлей
```

Миграции применятся автоматически (сервис `migrate`). Данные в томах (`pgdata`, `media`, `esdata`) сохраняются.

## 10. Бэкапы

```bash
# база данных
docker compose exec -T postgres sh -c 'pg_dump -U "$POSTGRES_USER" -Fc "$POSTGRES_DB"' > backup_$(date +%F).dump

# загруженные файлы
docker run --rm -v threadline_media:/media -v "$PWD":/out alpine tar czf /out/media_$(date +%F).tgz -C /media .
```

Ежедневный бэкап в 03:00 с ротацией 14 дней. Сначала создайте каталог: `mkdir -p ~/backups`. Затем `crontab -e`:

```cron
0 3 * * * cd /home/deploy/threadline && docker compose exec -T postgres sh -c 'pg_dump -U "$POSTGRES_USER" -Fc "$POSTGRES_DB"' > /home/deploy/backups/db_$(date +\%F).dump
5 3 * * * docker run --rm -v threadline_media:/media -v /home/deploy/backups:/out alpine tar czf /out/media_$(date +\%F).tgz -C /media .
30 3 * * * find /home/deploy/backups -type f -mtime +14 -delete
```

Восстановление (приложение на время восстановления останавливается):

```bash
docker compose stop backend realtime worker
docker compose exec -T postgres sh -c 'pg_restore -U "$POSTGRES_USER" -d "$POSTGRES_DB" --clean --if-exists' < backup_2026-10-22.dump
docker run --rm -v threadline_media:/media -v "$PWD":/in alpine tar xzf /in/media_2026-10-22.tgz -C /media
docker compose start backend realtime worker
docker compose exec backend python manage.py search_reindex
```

Индекс Elasticsearch бэкапить не нужно: его можно восстановить из БД командой `search_reindex`.

## 11. Логи и диагностика

```bash
docker compose logs -f backend realtime worker   # HTTP API, WebSocket и воркер
docker compose logs --tail=100 migrate    # почему не стартовал backend
```

| Симптом | Причина | Решение |
|---|---|---|
| `backend` не стартует, `migrate` exited (1) | БД или ES не готовы, неверный пароль | `docker compose logs migrate`, проверить `.env` |
| 400 Bad Request на всех страницах | Домена нет в `DJANGO_ALLOWED_HOSTS` | Добавить домен, `docker compose up -d` |
| Live-обновления не работают («офлайн») | WebSocket Origin не из `ALLOWED_HOSTS` | То же, что выше |
| Elasticsearch падает по OOM | Мало RAM | Увеличить RAM или уменьшить `ES_JAVA_OPTS` |
| Caddy не получает сертификат | DNS ещё не обновился или закрыт порт 80 | `dig`, `ufw status`, `docker compose logs caddy` |

## 12. Масштабирование на том же сервере

```bash
# больше процессов и потоков (в .env):
WEB_CONCURRENCY=4        # процессы gunicorn (≈ число ядер)
WEB_THREADS=8            # потоки на процесс
WORKER_CONCURRENCY=8     # процессы Celery

# или больше контейнеров:
docker compose up -d --scale backend=3 --scale realtime=2 --scale worker=2
docker compose restart frontend   # nginx перечитывает DNS и балансирует на все реплики
```

Стратегия для нескольких серверов описана в [scaling.md](scaling.md).

## 13. Поисковые системы

Подключите Google Search Console и отправьте `sitemap.xml`. Пошагово: [seo.md](seo.md#после-деплоя-google-search-console).
