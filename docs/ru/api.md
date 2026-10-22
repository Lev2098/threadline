# API

[← README](../../README.ru.md) · [Українська](../uk/api.md)

Интерактивная документация: **`/api/docs`** (Swagger UI, OpenAPI 3) и **`/graphql`** (GraphiQL).

## Аутентификация

Регистрации нет. Клиент получает анонимный JWT и передаёт его в заголовке `Authorization: Bearer <token>`. Токен обязателен для публикации и WebSocket; чтение доступно без него.

```http
POST /api/v1/session
→ 201 {"token": "eyJ…", "client_id": "9f2c…", "expires_in": 2592000}
```

## REST `/api/v1`

| Метод | Путь | Описание |
|---|---|---|
| `POST` | `/session` | Выдать анонимный токен |
| `GET` | `/captcha` | Новая одноразовая капча: `{key, image: "data:image/png;base64,…", ttl}` |
| `GET` | `/comments?page=1&ordering=-created_at` | Заглавные комментарии по 25. `ordering` ∈ `created_at`, `-created_at`, `username`, `-username`, `email`, `-email` |
| `POST` | `/comments` | Опубликовать (multipart). Нужен токен |
| `POST` | `/comments/preview` | `{text}` → `{html}`, рендер без сохранения |
| `GET` | `/comments/{root_id}/thread?cursor=` | Все ответы ветки в порядке обхода дерева. `next_cursor` для следующей порции |
| `GET` | `/comments/search?q=&page=` | Полнотекстовый поиск |

### Публикация

```bash
curl -X POST https://host/api/v1/comments \
  -H "Authorization: Bearer $TOKEN" \
  -F username=Anonym -F email=anon@example.com \
  -F home_page=https://example.com \
  -F 'text=Привет, <strong>мир</strong>' \
  -F captcha_key=$KEY -F captcha=Ab3dEf \
  -F parent_id=42 \
  -F attachment=@photo.jpg
```

### Формат ошибок

Ошибки имеют единый формат. Ошибки валидации возвращаются **по полям, все сразу**:

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

| HTTP | `code` | Когда |
|---|---|---|
| 400 | `invalid`, `invalid_markup`, `invalid_attachment`, `invalid_captcha` | Ошибка ввода |
| 401 | `not_authenticated`, `authentication_failed` | Нет токена или он просрочен (клиент просто берёт новый) |
| 404 | `not_found` | Нет родительского комментария или ветки |
| 413 | `too_large` | Файл больше лимита nginx (11 МБ) |
| 429 | `throttled` | Превышен лимит запросов (DRF или nginx) |
| 503 | `unavailable` | Зависимость временно недоступна (например, Elasticsearch для поиска) |

Этот формат одинаков для всех ошибок `/api/`, включая ошибки валидации параметров (`?page=0`), неизвестные пути (JSON 404), ошибки nginx (413, 429, 502–504) и внутренние ошибки (JSON 500).

## GraphQL `/graphql`

```graphql
query {
  comments(page: 1, ordering: USERNAME_ASC) {
    total pages
    items { id username email createdAt repliesCount html attachment { kind url width height } }
  }
  thread(rootId: 42) { items { id parentId depth username html } nextCursor }
  search(q: "кэш") { total items { id username html } }
}

mutation { previewComment(text: "<i>hi</i>") }
```

### Ограничения

| Что | Лимит |
|---|---|
| Глубина ветки | 100 уровней; ответ глубже возвращает 400 с полем `parent_id` |
| Текст | 5000 символов после нормализации переносов строк |
| Изображение | ≤ 10 МБ, ≤ 40 Мп; анимированный GIF ≤ 100 кадров |
| `cursor` ветки | только значение `next_cursor` из предыдущего ответа |
| Страница поиска | ≤ 400 (окно Elasticsearch в 10 000 совпадений) |
| GraphQL | глубина ≤ 6, алиасов ≤ 5, токенов ≤ 1000; GraphiQL только при `DJANGO_DEBUG=true` |

`replies_count` — количество **всех** ответов в ветке; заполняется для заглавных комментариев, для ответов равен 0.

## WebSocket `/ws/comments/?token=<JWT>`

Сервер отправляет каждый новый комментарий (и корни, и ответы) в том же формате, что и REST:

```json
{"type": "comment.posted", "comment": {"id": 101, "parent_id": 42, "root_id": 42, "depth": 1, "...": "..."}}
```

Клиент может отправлять `{"type": "ping"}` и получает `{"type": "pong"}`. Без валидного токена сервер принимает соединение и сразу закрывает его с кодом `4401`. Клиент по этому коду берёт новый токен и переподключается.
