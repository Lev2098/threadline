"""SEO metadata: URLs, texts and schema.org JSON-LD for server-rendered pages."""

from __future__ import annotations

import json
from typing import Any

from django.conf import settings

from comments.domain.comment import Comment

LANGS = ("uk", "ru")
DEFAULT_LANG = "uk"
SITE_NAME = "Threadline"

TEXTS: dict[str, dict[str, str]] = {
    "uk": {
        "home_title": "Threadline — обговорення, що ростуть гілками",
        "home_description": (
            "Відкриті обговорення з відповідями будь-якої глибини. Нові коментарі з’являються наживо, "
            "без перезавантаження сторінки."
        ),
        "home_heading": "Говоримо по суті.",
        "page": "Сторінка",
        "replies": "відповідей",
        "open_thread": "Відкрити гілку",
        "prev": "Попередня сторінка",
        "next": "Наступна сторінка",
        "back": "До всіх обговорень",
        "not_found_title": "Обговорення не знайдено",
        "not_found_text": "Можливо, посилання застаріло. Перегляньте всі обговорення.",
        "thread_suffix": "обговорення",
        "attachment": "Вкладення",
    },
    "ru": {
        "home_title": "Threadline — обсуждения, которые растут ветками",
        "home_description": (
            "Открытые обсуждения с ответами любой глубины. Новые комментарии появляются вживую, "
            "без перезагрузки страницы."
        ),
        "home_heading": "Говорим по делу.",
        "page": "Страница",
        "replies": "ответов",
        "open_thread": "Открыть ветку",
        "prev": "Предыдущая страница",
        "next": "Следующая страница",
        "back": "Ко всем обсуждениям",
        "not_found_title": "Обсуждение не найдено",
        "not_found_text": "Возможно, ссылка устарела. Посмотрите все обсуждения.",
        "thread_suffix": "обсуждение",
        "attachment": "Вложение",
    },
}


def site_url() -> str:
    return str(settings.SITE_URL).rstrip("/")


def absolute(path: str) -> str:
    return f"{site_url()}{path}"


def with_lang(path: str, lang: str, **params: Any) -> str:
    """Canonical form: default language has no ``lang`` parameter."""
    query = {key: value for key, value in params.items() if value not in (None, "", 1, "1")}
    if lang != DEFAULT_LANG:
        query["lang"] = lang
    if not query:
        return path
    return path + "?" + "&".join(f"{key}={value}" for key, value in query.items())


def thread_path(comment_id: int) -> str:
    return f"/t/{comment_id}"


def excerpt(text: str, limit: int) -> str:
    text = " ".join(text.split())
    if len(text) <= limit:
        return text
    cut = text[: limit - 1].rsplit(" ", 1)[0]
    return f"{cut}…"


def json_ld(data: dict[str, Any]) -> str:
    """Serialize for <script type="application/ld+json"> without allowing a
    comment's text to close the script element."""
    raw = json.dumps(data, ensure_ascii=False, separators=(",", ":"))
    return raw.replace("<", "\\u003c").replace(">", "\\u003e").replace("&", "\\u0026")


def person(comment: Comment) -> dict[str, Any]:
    data: dict[str, Any] = {"@type": "Person", "name": comment.author.username.value}
    if comment.author.home_page:
        data["url"] = comment.author.home_page.value
    return data


def website_ld(lang: str) -> dict[str, Any]:
    return {
        "@context": "https://schema.org",
        "@type": "WebSite",
        "name": SITE_NAME,
        "url": absolute("/"),
        "inLanguage": lang,
        "potentialAction": {
            "@type": "SearchAction",
            "target": {"@type": "EntryPoint", "urlTemplate": absolute("/?q={search_term_string}")},
            "query-input": "required name=search_term_string",
        },
    }


def discussion_ld(root: Comment, replies: list[Comment], lang: str) -> dict[str, Any]:
    assert root.id is not None
    url = absolute(thread_path(root.id))
    data: dict[str, Any] = {
        "@context": "https://schema.org",
        "@type": "DiscussionForumPosting",
        "@id": url,
        "url": url,
        "mainEntityOfPage": url,
        "headline": excerpt(root.text.plain, 110),
        "text": root.text.plain,
        "inLanguage": lang,
        "author": person(root),
        "datePublished": root.created_at.isoformat() if root.created_at else None,
        "interactionStatistic": {
            "@type": "InteractionCounter",
            "interactionType": "https://schema.org/CommentAction",
            "userInteractionCount": root.replies_count,
        },
        "comment": [
            {
                "@type": "Comment",
                "@id": f"{url}#c{reply.id}",
                "text": reply.text.plain,
                "author": person(reply),
                "datePublished": reply.created_at.isoformat() if reply.created_at else None,
            }
            for reply in replies[:100]
        ],
    }
    if root.attachment and root.attachment.kind.value == "image":
        data["image"] = absolute(settings.MEDIA_URL + root.attachment.path)
    return data
