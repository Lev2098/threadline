# Threadline — SPA-коментарі з деревовидними відповідями

**Українська** · [Русский](README.ru.md)

Односторінковий застосунок, де користувачі залишають коментарі та відповідають на них на будь-якій глибині. Нові повідомлення з'являються в усіх відкритих вкладках наживо, без перезавантаження.

Бекенд: Django у **гексагональній архітектурі** (ports & adapters). Фронтенд: Vue 3. Усе оточення піднімається однією командою `docker compose up`.

![thread](docs/img/thread.png)

| Головна | Форма (темна тема) |
|---|---|
| ![home](docs/img/home.png) | ![composer](docs/img/composer-dark.png) |
| **Lightbox** | **Мобільна версія** |
| ![lightbox](docs/img/lightbox.png) | <img src="docs/img/mobile.png" width="260" alt="mobile"> |

---

## Зміст

- [Можливості](#можливості)
- [Як виконано вимоги ТЗ](#як-виконано-вимоги-тз)
- [Стек](#стек)
- [Швидкий старт (локально)](#швидкий-старт-локально)
- [Розгортання на сервері](#розгортання-на-сервері)
- [Структура проєкту](#структура-проєкту)
- [Тести та якість коду](#тести-та-якість-коду)
- [Документація](#документація)

## Можливості

- **Каскадні відповіді будь-якої глибини.** Кожна гілка з'єднана «нитками», а відповідь на відповідь показує цитату батьківського коментаря.
- **Таблиця заголовних коментарів.** Сортування за User Name, E-mail і датою в обидва боки, за замовчуванням LIFO. По 25 записів на сторінку.
- **Форма.** Поля User Name (латиниця й цифри), E-mail, Home page (необов'язкове), CAPTCHA-картинка і текст. Валідація відбувається і на клієнті, і на сервері.
- **Дозволені теги** `<a href title>`, `<i>`, `<strong>`, `<code>`. Є панель кнопок `[i] [strong] [code] [a]`, перевірка закриття тегів і валідного XHTML.
- **Попередній перегляд.** Повідомлення рендерить сервер рівно так, як воно буде збережене, без перезавантаження сторінки.
- **Файли.** Картинки JPG/GIF/PNG пропорційно зменшуються до 320×240 (анімація GIF зберігається). TXT приймається до 100 КБ. Перегляд відкривається в lightbox, який зумує зображення прямо з мініатюри.
- **Live-оновлення через WebSocket.** Новий корінь «в'їжджає» в таблицю, нова відповідь «проростає» по нитці. Якщо ви на іншій сторінці чи з іншим сортуванням, з'являється плашка «N нових коментарів».
- **Повнотекстовий пошук** на Elasticsearch.
- **Інтерфейс UA/RU**, світла й темна тема, адаптивна верстка до 360 px, доступність з клавіатури, підтримка `prefers-reduced-motion`.
- **API:** REST з OpenAPI/Swagger (`/api/docs`), GraphQL (`/graphql`), WebSocket (`/ws/comments/`).
- **SEO.** Кожна гілка має власну адресу `/t/<id>` і віддається сервером як готовий HTML: meta, Open Graph, JSON-LD `DiscussionForumPosting`, hreflang uk/ru. Є `robots.txt`, `sitemap.xml` на сотні тисяч гілок і справжні 404. Lighthouse: desktop 100/100/100/100, mobile 94–95/100/100/100. Деталі — [docs/uk/seo.md](docs/uk/seo.md).
- **Анімації й дрібні радощі** (усі вимикаються при `prefers-reduced-motion`): заголовок з'являється по словах, лічильник «докручується», гілки «проростають», тема змінюється кругом від кнопки, при публікації розлітається конфеті, по таблиці йде spotlight за курсором. Гарячі клавіші: `/` пошук, `n` нове обговорення, `t` тема, `?` довідка.

## Як виконано вимоги ТЗ

| Вимога | Реалізація |
|---|---|
| ООП, SQL | Доменні сутності та value objects, use case-класи, порти-протоколи. PostgreSQL 17 |
| Дані про користувача | `username`, `email`, `home_page`, а також `client_id` (анонімний JWT), `ip`, `user_agent` |
| Каскадне відображення | Materialized path + `root_id`: уся гілка читається одним індексним запитом |
| Таблиця, сортування, LIFO, 25 на сторінку | Часткові індекси під кожне поле сортування, deferred join для глибоких сторінок |
| XSS | Allow-list парсер (стек тегів, перевірка `href`), повторна серіалізація, `nh3` на сервері, DOMPurify у браузері, CSP |
| SQL-ін'єкції | Лише ORM і параметризовані запити, сортування з allow-list |
| CAPTCHA | Власна генерація (Pillow), одноразова, у Redis з TTL, атомарний `GETDEL` |
| Файли | Тип визначається за magic bytes, захист від decompression bomb, EXIF прибирається |
| Валідація на клієнті й сервері | TypeScript-дзеркало правил; сервер лишається джерелом істини і повертає помилки по полях |
| Django, Django ORM, Vue, Docker, Git, WebSocket | Так. Історія Git з feature-гілками й merge-комітами |
| **Junior+:** Queue, Cache, Events, JWT | Celery-черга; Redis-кеш з версійною інвалідацією; доменна подія `CommentPosted`; анонімні JWT-сесії |
| **Middle:** GraphQL, брокер, NoSQL, Cloud | Strawberry GraphQL; RabbitMQ; Elasticsearch + Redis; готовий до будь-якого VDS/хмари (Docker + Caddy HTTPS) |
| **Middle+:** 1 000 000 повідомлень, 100 тис. користувачів на добу | Архітектура в [docs/uk/scaling.md](docs/uk/scaling.md); Locust-тест з SLO-перевіркою в `loadtest/` |
| Схема БД для MySQL Workbench | [docs/db/schema.mysql.sql](docs/db/schema.mysql.sql) |

## Стек

**Backend:** Python 3.12 · Django 5.2 · DRF + drf-spectacular · Strawberry GraphQL · Channels · Celery · PostgreSQL 17 · Redis 7 · RabbitMQ 4 · Elasticsearch 8 · Pillow · nh3 · PyJWT · gunicorn (HTTP) + uvicorn (WebSocket)
**Frontend:** Vue 3.5 · TypeScript · Vite 6 · DOMPurify
**Infra:** Docker multi-stage · docker compose · nginx (edge proxy, CSP, rate limit) · Caddy (HTTPS) · Locust

## Швидкий старт (локально)

Потрібен лише Docker (Docker Desktop або Docker Engine з плагіном compose).

```bash
git clone <repo-url> threadline && cd threadline
cp .env.example .env                 # для локального запуску досить замінити паролі
docker compose up -d --build         # перший запуск 3–5 хв
```

| Що | Адреса |
|---|---|
| Застосунок | http://localhost:8080 |
| Swagger / OpenAPI | http://localhost:8080/api/docs |
| GraphQL (GraphiQL) | http://localhost:8080/graphql |
| Django admin | http://localhost:8080/admin/ (`docker compose exec backend python manage.py createsuperuser`) |
| RabbitMQ UI | http://localhost:15672 (логін і пароль з `.env`) |

Демо-дані:

```bash
docker compose exec backend python manage.py seed_comments --count 5000
docker compose exec backend python manage.py search_reindex
```

## Розгортання на сервері

Покрокова інструкція (VDS з Ubuntu, домен, HTTPS, оновлення, бекапи): **[docs/uk/deployment.md](docs/uk/deployment.md)**.

Коротко:

```bash
cp .env.example .env    # заповнити секрети, DOMAIN, DJANGO_ALLOWED_HOSTS
docker compose -f docker-compose.yml -f docker-compose.prod.yml up -d --build
```

## Структура проєкту

```
backend/
  src/comments/
    domain/          # чистий Python: Comment, UserName/Email/HomePage, CommentText (XHTML), Upload
    application/     # use cases + порти (typing.Protocol)
    adapters/
      inbound/       # REST, GraphQL, WebSocket, Celery tasks, management-команди
      outbound/      # ORM-репозиторій, кеш, капча, Pillow, nh3, Elasticsearch, RabbitMQ, Channels
    bootstrap.py     # composition root: який адаптер стоїть за яким портом
  src/config/        # Django settings (12-factor), ASGI, Celery
  tests/             # unit (без БД) + integration (API, WebSocket)
frontend/            # Vue 3 SPA + nginx.conf
loadtest/            # Locust-сценарій і скрипт прогону
deploy/              # Caddyfile для HTTPS
docs/                # документація UA/RU, схема БД
docker-compose.yml           # повний стек
docker-compose.prod.yml      # продакшн-оверлей (HTTPS)
docker-compose.loadtest.yml  # оверлей для навантажувального тесту
```

## Тести та якість коду

```bash
# У Docker, на справжніх PostgreSQL + Redis:
docker compose --profile test run --rm tests

# Або локально (SQLite + in-memory адаптери, без жодних сервісів):
cd backend && pip install -e '.[dev]' && pytest           # Python ≥ 3.12

ruff check src tests && mypy src && lint-imports          # стиль, типи (strict), межі гексагона
cd ../frontend && npm ci && npm run typecheck
```

- **134 тести.** Юніт-тести домену та use cases з in-memory фейками, без Django і БД. Інтеграційні тести REST, GraphQL і WebSocket. Окремий набір регресійних тестів на кожен баг, знайдений під час QA.
- **`import-linter` перевіряє межі гексагона.** Домен і застосунок не можуть імпортувати Django, Redis, Celery тощо. Шари не можуть імпортувати «вгору».
- **mypy у strict-режимі.**

## Документація

| Документ | Українською | По-русски |
|---|---|---|
| Архітектура та рішення (ADR) | [docs/uk/architecture.md](docs/uk/architecture.md) | [docs/ru/architecture.md](docs/ru/architecture.md) |
| Розгортання крок за кроком | [docs/uk/deployment.md](docs/uk/deployment.md) | [docs/ru/deployment.md](docs/ru/deployment.md) |
| Масштабування та навантажувальний тест | [docs/uk/scaling.md](docs/uk/scaling.md) | [docs/ru/scaling.md](docs/ru/scaling.md) |
| API: REST, GraphQL, WebSocket | [docs/uk/api.md](docs/uk/api.md) | [docs/ru/api.md](docs/ru/api.md) |
| SEO та індексація | [docs/uk/seo.md](docs/uk/seo.md) | [docs/ru/seo.md](docs/ru/seo.md) |
| QA: як перевірявся продукт | [docs/uk/qa.md](docs/uk/qa.md) | [docs/ru/qa.md](docs/ru/qa.md) |
| Сценарій демо-відео | [docs/uk/video.md](docs/uk/video.md) | [docs/ru/video.md](docs/ru/video.md) |
| Схема БД | [docs/db/schema.mysql.sql](docs/db/schema.mysql.sql) (Workbench) · [docs/db/schema.postgresql.sql](docs/db/schema.postgresql.sql) (фактична) | |
