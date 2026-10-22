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
| 429 | `throttled` | Перевищено ліміт запитів |

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

## WebSocket `/ws/comments/?token=<JWT>`

Сервер надсилає кожен новий коментар (і корені, і відповіді) у тому ж форматі, що й REST:

```json
{"type": "comment.posted", "comment": {"id": 101, "parent_id": 42, "root_id": 42, "depth": 1, "...": "..."}}
```

Клієнт може надсилати `{"type": "ping"}` і отримує `{"type": "pong"}`. Без валідного токена з'єднання закривається з кодом `4401`.
