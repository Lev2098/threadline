# Розгортання крок за кроком

[← README](../../README.md) · [Русский](../ru/deployment.md)

Інструкція розрахована на чистий VDS з **Ubuntu 22.04/24.04**. На іншому Linux з Docker кроки ті самі.

## 0. Що знадобиться

| Ресурс | Мінімум | Рекомендовано |
|---|---|---|
| CPU | 2 vCPU | 4 vCPU |
| RAM | 4 ГБ (Elasticsearch бере ~1 ГБ) | 8 ГБ |
| Диск | 20 ГБ SSD | 40 ГБ SSD |
| Домен | необов'язково (можна по IP) | так, для HTTPS |

## 1. DNS (якщо є домен)

У панелі реєстратора створіть **A-запис** `comments.example.com → <IP сервера>`. Перевірка:

```bash
dig +short comments.example.com     # має повернути IP сервера
```

## 2. Підготовка сервера

```bash
ssh root@<IP>

# оновлення системи
apt update && apt -y upgrade

# окремий користувач замість root
adduser deploy
usermod -aG sudo deploy

# фаєрвол: SSH, HTTP, HTTPS
ufw allow OpenSSH
ufw allow 80/tcp
ufw allow 443/tcp
ufw allow 443/udp
ufw --force enable
```

## 3. Встановлення Docker

```bash
curl -fsSL https://get.docker.com | sh
usermod -aG docker deploy
su - deploy                          # перелогінитись, щоб група застосувалась
docker --version && docker compose version
```

## 4. Код

```bash
git clone <repo-url> threadline
cd threadline
```

## 5. Налаштування `.env`

```bash
cp .env.example .env

# згенерувати секрети
sed -i "s|^DJANGO_SECRET_KEY=.*|DJANGO_SECRET_KEY=$(openssl rand -hex 32)|" .env
sed -i "s|^JWT_SECRET=.*|JWT_SECRET=$(openssl rand -hex 32)|" .env
sed -i "s|^POSTGRES_PASSWORD=.*|POSTGRES_PASSWORD=$(openssl rand -hex 16)|" .env
sed -i "s|^RABBITMQ_PASSWORD=.*|RABBITMQ_PASSWORD=$(openssl rand -hex 16)|" .env
nano .env
```

Відредагуйте в `.env` (і розкоментуйте ці рядки):

```dotenv
DJANGO_ALLOWED_HOSTS=comments.example.com
DJANGO_CSRF_TRUSTED_ORIGINS=https://comments.example.com
DOMAIN=comments.example.com
SITE_URL=https://comments.example.com
BEHIND_TLS_PROXY=true
SECURE_COOKIES=true
COMPOSE_FILE=docker-compose.yml:docker-compose.prod.yml
```

`COMPOSE_FILE` робить продакшн-оверлей (Caddy + HTTPS, закриті порти застосунку) частиною **кожної** команди `docker compose …` на цьому сервері. Без нього `docker compose up -d` під час оновлення чи масштабування тихо повернув би стек у локальний режим із відкритим портом 8080.

> **Без домену** (лише IP): `DJANGO_ALLOWED_HOSTS=<IP>`, `DJANGO_CSRF_TRUSTED_ORIGINS=http://<IP>:8080`, рядки `DOMAIN`, `BEHIND_TLS_PROXY`, `SECURE_COOKIES` і `COMPOSE_FILE` не додавайте. Сайт буде на `http://<IP>:8080`.

> **Docker і ufw.** Порти, які публікує Docker, обходять правила ufw. Тому продакшн-оверлей не публікує нічого, крім 80/443 (Caddy), а RabbitMQ UI слухає лише `127.0.0.1` (доступ через `ssh -L 15672:localhost:15672`).

> **Підмережа.** Стек використовує мережу `172.28.0.0/24` (Caddy має фіксовану адресу `172.28.0.250`, лише їй nginx довіряє `X-Forwarded-For`). Якщо на сервері ця підмережа зайнята, задайте в `.env` `COMPOSE_SUBNET` і `CADDY_IP`.

## 6. Запуск

```bash
docker compose up -d --build
```

Перший запуск займає 3–5 хвилин (збірка образів). Сервіс `migrate` сам застосує міграції, збере статику й створить індекс Elasticsearch, а `backend` стартує лише після цього.

## 7. Перевірка

```bash
docker compose ps -a                 # усі сервіси running (healthy), migrate: exited (0)
curl -s https://comments.example.com/readyz     # {"status": "ready"}
```

Відкрийте `https://comments.example.com` і залиште коментар. Відкрийте сайт у другій вкладці: новий коментар з'явиться там без перезавантаження.

## 8. Адміністратор і демо-дані (за бажанням)

```bash
docker compose exec backend python manage.py createsuperuser
docker compose exec backend python manage.py seed_comments --count 5000
docker compose exec backend python manage.py search_reindex
```

## 9. Оновлення

```bash
cd ~/threadline
git pull
docker compose up -d --build        # COMPOSE_FILE з .env додає продакшн-оверлей
```

Міграції застосуються автоматично (сервіс `migrate`). Дані в томах (`pgdata`, `media`, `esdata`) зберігаються.

## 10. Бекапи

```bash
# база даних
docker compose exec -T postgres sh -c 'pg_dump -U "$POSTGRES_USER" -Fc "$POSTGRES_DB"' > backup_$(date +%F).dump

# завантажені файли
docker run --rm -v threadline_media:/media -v "$PWD":/out alpine tar czf /out/media_$(date +%F).tgz -C /media .
```

Щоденний бекап о 03:00 з ротацією 14 днів. Спершу створіть каталог: `mkdir -p ~/backups`. Потім `crontab -e`:

```cron
0 3 * * * cd /home/deploy/threadline && docker compose exec -T postgres sh -c 'pg_dump -U "$POSTGRES_USER" -Fc "$POSTGRES_DB"' > /home/deploy/backups/db_$(date +\%F).dump
5 3 * * * docker run --rm -v threadline_media:/media -v /home/deploy/backups:/out alpine tar czf /out/media_$(date +\%F).tgz -C /media .
30 3 * * * find /home/deploy/backups -type f -mtime +14 -delete
```

Відновлення (застосунок на час відновлення зупиняється):

```bash
docker compose stop backend realtime worker
docker compose exec -T postgres sh -c 'pg_restore -U "$POSTGRES_USER" -d "$POSTGRES_DB" --clean --if-exists' < backup_2026-10-22.dump
docker run --rm -v threadline_media:/media -v "$PWD":/in alpine tar xzf /in/media_2026-10-22.tgz -C /media
docker compose start backend realtime worker
docker compose exec backend python manage.py search_reindex
```

Індекс Elasticsearch бекапити не потрібно: його можна відновити з БД командою `search_reindex`.

## 11. Логи та діагностика

```bash
docker compose logs -f backend realtime worker   # HTTP API, WebSocket і воркер
docker compose logs --tail=100 migrate    # чому не стартував backend
```

| Симптом | Причина | Рішення |
|---|---|---|
| `backend` не стартує, `migrate` exited (1) | БД або ES не готові, невірний пароль | `docker compose logs migrate`, перевірити `.env` |
| 400 Bad Request на всіх сторінках | Домену немає в `DJANGO_ALLOWED_HOSTS` | Додати домен, `docker compose up -d` |
| Live-оновлення не працюють («офлайн») | WebSocket Origin не з `ALLOWED_HOSTS` | Те саме, що вище |
| Elasticsearch падає з OOM | Мало RAM | Збільшити RAM або зменшити `ES_JAVA_OPTS` |
| Caddy не отримує сертифікат | DNS ще не оновився або закритий порт 80 | `dig`, `ufw status`, `docker compose logs caddy` |

## 12. Масштабування на тому ж сервері

```bash
# більше процесів і потоків (у .env):
WEB_CONCURRENCY=4        # процеси gunicorn (≈ кількість ядер)
WEB_THREADS=8            # потоки на процес
WORKER_CONCURRENCY=8     # процеси Celery

# або більше контейнерів:
docker compose up -d --scale backend=3 --scale realtime=2 --scale worker=2
docker compose restart frontend   # nginx перечитує DNS і балансує на всі репліки
```

Стратегію для кількох серверів описано в [scaling.md](scaling.md).

## 13. Пошукові системи

Підключіть Google Search Console і надішліть `sitemap.xml`. Покроково: [seo.md](seo.md#після-деплою-google-search-console).
