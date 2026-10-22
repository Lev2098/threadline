# API

[← README](../../README.md) · [Русский](../ru/api.md)

Інтерактивна документація: **`/api/docs`** (Swagger UI, OpenAPI 3) і **`/graphql`** (GraphiQL).

## Автентифікація

Реєстрації немає. Клієнт отримує анонімний JWT і передає його в заголовку `Authorization: Bearer <token>`. Токен обов'язковий для публікації та WebSocket; читання доступне без нього.

```http
POST /api/v1/session
→ 201 {"token": "eyJ…", "client_id": "9f2c…", "expires_in": 2592000}
```

## REST `/api/v1`

| Метод | Шлях | Опис |
|---|---|---|
| `POST` | `/session` | Видати анонімний токен |
| `GET` | `/captcha` | Нова одноразова капча: `{key, image: "data:image/png;base64,…", ttl}` |
| `GET` | `/comments?page=1&ordering=-created_at` | Заголовні коментарі по 25. `ordering` ∈ `created_at`, `-created_at`, `username`, `-username`, `email`, `-email` |
| `POST` | `/comments` | Опублікувати (multipart). Потрібен токен |
| `POST` | `/comments/preview` | `{text}` → `{html}`, рендер без збереження |
| `GET` | `/comments/{root_id}/thread?cursor=` | Усі відповіді гілки в порядку обходу дерева. `next_cursor` для наступної порції |
| `GET` | `/comments/search?q=&page=` | Повнотекстовий пошук |

### Публікація

```bash
curl -X POST https://host/api/v1/comments \
  -H "Authorization: Bearer $TOKEN" \
  -F username=Anonym -F email=anon@example.com \
  -F home_page=https://example.com \
  -F 'text=Привіт, <strong>світ</strong>' \
  -F captcha_key=$KEY -F captcha=Ab3dEf \
  -F parent_id=42 \
  -F attachment=@photo.jpg
```

### Формат помилок

Помилки мають єдиний формат. Помилки валідації повертаються **по полях, усі одразу**:

```json
{
  "code": "invalid",
  "message": "Please fix the highlighted fields.",
  "errors": {
    "username": "User name may contain only Latin letters and digits.",
    "text": "Tag <script> is not allowed. Allowed tags: a, code, i, strong."
  }
}
```

| HTTP | `code` | Коли |
|---|---|---|
| 400 | `invalid`, `invalid_markup`, `invalid_attachment`, `invalid_captcha` | Помилка вводу |
| 401 | `not_authenticated`, `authentication_failed` | Немає токена або він прострочений (клієнт просто бере новий) |
| 404 | `not_found` | Немає батьківського коментаря або гілки |
| 413 | `too_large` | Файл більший за ліміт nginx (11 МБ) |
| 429 | `throttled` | Перевищено ліміт запитів (DRF або nginx) |
| 503 | `unavailable` | Залежність тимчасово недоступна (наприклад, Elasticsearch для пошуку) |

Цей формат однаковий для всіх помилок `/api/`, зокрема для помилок валідації параметрів (`?page=0`), невідомих шляхів (JSON 404), помилок nginx (413, 429, 502–504) і внутрішніх помилок (JSON 500).

## GraphQL `/graphql`

```graphql
query {
  comments(page: 1, ordering: USERNAME_ASC) {
    total pages
    items { id username email createdAt repliesCount html attachment { kind url width height } }
  }
  thread(rootId: 42) { items { id parentId depth username html } nextCursor }
  search(q: "кеш") { total items { id username html } }
}

mutation { previewComment(text: "<i>hi</i>") }
```

### Обмеження

| Що | Ліміт |
|---|---|
| Глибина гілки | 100 рівнів; відповідь глибше повертає 400 з полем `parent_id` |
| Текст | 5000 символів після нормалізації переносів рядка |
| Зображення | ≤ 10 МБ, ≤ 40 Мп; анімований GIF ≤ 100 кадрів |
| `cursor` гілки | лише значення `next_cursor` з попередньої відповіді |
| Сторінка пошуку | ≤ 400 (вікно Elasticsearch у 10 000 збігів) |
| GraphQL | глибина ≤ 6, аліасів ≤ 3, токенів ≤ 1000; GraphiQL лише при `DJANGO_DEBUG=true` |

`replies_count` — кількість **усіх** відповідей у гілці; заповнюється для заголовних коментарів, для відповідей дорівнює 0.

## WebSocket `/ws/comments/?token=<JWT>`

Сервер надсилає кожен новий коментар (і корені, і відповіді) у тому ж форматі, що й REST:

```json
{"type": "comment.posted", "comment": {"id": 101, "parent_id": 42, "root_id": 42, "depth": 1, "...": "..."}}
```

Клієнт може надсилати `{"type": "ping"}` і отримує `{"type": "pong"}`. Без валідного токена сервер приймає з'єднання й одразу закриває його з кодом `4401`. Клієнт по цьому коду бере новий токен і перепідключається.
