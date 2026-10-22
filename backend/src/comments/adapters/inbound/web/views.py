"""Server-rendered pages: the same use cases as the API, rendered as HTML.

Crawlers and first-time visitors get complete, indexable content with proper
status codes; the SPA then boots on top and reuses the embedded data
(``#tl-initial``) instead of fetching it again.
"""

from __future__ import annotations

import math
from typing import Any
from xml.sax.saxutils import escape

from django.conf import settings
from django.http import HttpRequest, HttpResponse, HttpResponsePermanentRedirect, HttpResponseRedirect
from django.template.loader import render_to_string
from django.utils import timezone
from django.views.decorators.cache import cache_page
from django.views.decorators.http import require_GET

from comments.adapters.inbound.rest.views import page_payload
from comments.adapters.inbound.web import seo
from comments.adapters.inbound.web.shell import render_into_shell
from comments.adapters.serialization import comment_to_dict
from comments.application.dto import ListRootsQuery
from comments.bootstrap import container
from comments.domain.comment import Comment
from comments.domain.errors import NotFoundError
from comments.domain.values import Ordering, SortDirection, SortField

SITEMAP_PAGE_SIZE = 5000
HTML_MAX_AGE = 60
OG_LOCALES = {"uk": "uk_UA", "ru": "ru_RU"}


def _lang(request: HttpRequest) -> str:
    lang = request.GET.get("lang", seo.DEFAULT_LANG)
    return lang if lang in seo.LANGS else seo.DEFAULT_LANG


def _alternates(path: str, **params: Any) -> list[dict[str, str]]:
    links = [{"hreflang": lang, "href": seo.absolute(seo.with_lang(path, lang, **params))} for lang in seo.LANGS]
    links.append({"hreflang": "x-default", "href": seo.absolute(seo.with_lang(path, seo.DEFAULT_LANG, **params))})
    return links


def _date(comment: Comment) -> tuple[str, str]:
    created = timezone.localtime(comment.created_at) if comment.created_at else None
    return (created.isoformat(), created.strftime("%d.%m.%Y %H:%M")) if created else ("", "")


def _html_response(head: dict[str, Any], body: str, lang: str, status: int = 200) -> HttpResponse:
    head = {
        "og_type": "website",
        "og_image": seo.absolute("/og-image.png"),
        "og_locale": OG_LOCALES[lang],
        "robots": "index,follow",
        **head,
    }
    html = render_into_shell(render_to_string("seo/head.html", head), body, lang)
    response = HttpResponse(html, status=status, content_type="text/html; charset=utf-8")
    response["Content-Language"] = lang
    response["Cache-Control"] = f"public, max-age={HTML_MAX_AGE}" if status == 200 else "no-store"
    return response


@require_GET
def home(request: HttpRequest) -> HttpResponse:
    lang = _lang(request)
    text = seo.TEXTS[lang]
    try:
        requested = max(1, int(request.GET.get("page", "1")))
    except ValueError:
        requested = 1
    result = container().list_root_comments(ListRootsQuery(page=requested))
    if requested != result.page:  # past the last page
        return HttpResponseRedirect(seo.with_lang("/", lang, page=result.page))

    # Sorted or search views are client-side states: crawlable but not indexed,
    # so the index holds one canonical URL per page of content.
    secondary = bool(request.GET.get("ordering") or request.GET.get("q"))

    def path_for(page: int) -> str:
        return seo.with_lang("/", lang, page=page)

    prev_url = seo.absolute(path_for(result.page - 1)) if result.page > 1 else None
    next_url = seo.absolute(path_for(result.page + 1)) if result.page < result.pages else None
    title = text["home_title"] if result.page == 1 else f"{text['home_title']} — {text['page']} {result.page}"

    items = []
    for comment in result.items:
        assert comment.id is not None
        iso, date = _date(comment)
        items.append(
            {
                "url": seo.with_lang(seo.thread_path(comment.id), lang),
                "headline": seo.excerpt(comment.text.plain, 120),
                "username": comment.author.username.value,
                "iso": iso,
                "date": date,
                "replies": comment.replies_count,
            }
        )
    body = render_to_string(
        "seo/home_body.html",
        {
            "text": text,
            "items": items,
            "page": result.page,
            "pages": result.pages,
            "prev_url": prev_url,
            "next_url": next_url,
            "initial": {"view": "home", "ordering": "-created_at", "page": page_payload(result)},
        },
    )
    head = {
        "title": title,
        "description": text["home_description"],
        "canonical": seo.absolute(path_for(result.page)),
        "robots": "noindex,follow" if secondary else "index,follow",
        "alternates": _alternates("/", page=result.page),
        "prev_url": prev_url,
        "next_url": next_url,
        "json_ld": [seo.json_ld(seo.website_ld(lang))] if result.page == 1 else [],
    }
    return _html_response(head, body, lang)


@require_GET
def thread(request: HttpRequest, comment_id: int) -> HttpResponse:
    lang = _lang(request)
    text = seo.TEXTS[lang]
    try:
        comment = container().get_comment(comment_id)
        if not comment.is_root:
            # Permalink to a reply: canonical home is its thread, scrolled to it.
            target = seo.with_lang(seo.thread_path(comment.root_id or comment_id), lang)
            return HttpResponsePermanentRedirect(f"{target}#c{comment_id}")
        slice_ = container().get_thread(comment_id)
    except NotFoundError:
        return _not_found(lang)

    root, replies = comment, slice_.items
    assert root.id is not None
    headline = seo.excerpt(root.text.plain, 70)
    iso, date = _date(root)
    root_ctx: dict[str, Any] = {
        "id": root.id,
        "username": root.author.username.value,
        "iso": iso,
        "date": date,
        "replies": root.replies_count,
        "html": root.text.html,  # sanitized at write time (validator + nh3)
        "image": None,
    }
    if root.attachment and root.attachment.kind.value == "image":
        root_ctx["image"] = {
            "url": settings.MEDIA_URL + root.attachment.path,
            "name": root.attachment.original_name,
            "width": root.attachment.width,
            "height": root.attachment.height,
        }
    reply_ctx = []
    for reply in replies:
        r_iso, r_date = _date(reply)
        reply_ctx.append(
            {
                "id": reply.id,
                "username": reply.author.username.value,
                "iso": r_iso,
                "date": r_date,
                "html": reply.text.html,
                "indent": min(reply.depth - 1, 8) * 1.5,
            }
        )
    body = render_to_string(
        "seo/thread_body.html",
        {
            "text": text,
            "headline": headline,
            "root": root_ctx,
            "replies": reply_ctx,
            "home_url": seo.with_lang("/", lang),
            "initial": {
                "view": "thread",
                "root": comment_to_dict(root),
                "thread": {"items": [comment_to_dict(r) for r in replies], "next_cursor": slice_.next_cursor},
            },
        },
    )
    path = seo.thread_path(root.id)
    head = {
        "title": f"{headline} — Threadline",
        "description": seo.excerpt(root.text.plain, 160),
        "canonical": seo.absolute(seo.with_lang(path, lang)),
        "alternates": _alternates(path),
        "og_type": "article",
        "og_image": seo.absolute(root_ctx["image"]["url"]) if root_ctx["image"] else seo.absolute("/og-image.png"),
        "json_ld": [seo.json_ld(seo.discussion_ld(root, replies, lang))],
    }
    return _html_response(head, body, lang)


def _not_found(lang: str) -> HttpResponse:
    text = seo.TEXTS[lang]
    body = render_to_string("seo/not_found_body.html", {"text": text, "home_url": seo.with_lang("/", lang)})
    head = {
        "title": f"{text['not_found_title']} — Threadline",
        "description": text["not_found_text"],
        "canonical": seo.absolute("/"),
        "robots": "noindex,follow",
        "alternates": [],
        "json_ld": [],
    }
    return _html_response(head, body, lang, status=404)


@require_GET
def robots_txt(request: HttpRequest) -> HttpResponse:
    lines = [
        "User-agent: *",
        "Allow: /",
        "Disallow: /api/",
        "Disallow: /graphql",
        "Disallow: /admin/",
        "Disallow: /ws/",
        # Sorted and search views duplicate the canonical pages.
        "Disallow: /*?*ordering=",
        "Disallow: /*?*q=",
        "",
        f"Sitemap: {seo.absolute('/sitemap.xml')}",
        "",
    ]
    response = HttpResponse("\n".join(lines), content_type="text/plain; charset=utf-8")
    response["Cache-Control"] = "public, max-age=3600"
    return response


@require_GET
@cache_page(3600)
def sitemap_index(request: HttpRequest) -> HttpResponse:
    total = container().list_root_comments(ListRootsQuery(page=1, page_size=1)).total
    files = max(1, math.ceil(total / SITEMAP_PAGE_SIZE))
    now = timezone.now().date().isoformat()
    entries = [f"<sitemap><loc>{escape(seo.absolute('/sitemaps/pages.xml'))}</loc><lastmod>{now}</lastmod></sitemap>"]
    entries += [
        f"<sitemap><loc>{escape(seo.absolute(f'/sitemaps/threads-{n}.xml'))}</loc></sitemap>"
        for n in range(1, files + 1)
    ]
    return _xml(
        '<?xml version="1.0" encoding="UTF-8"?>\n'
        '<sitemapindex xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">' + "".join(entries) + "</sitemapindex>"
    )


@require_GET
@cache_page(3600)
def sitemap_pages(request: HttpRequest) -> HttpResponse:
    total_pages = container().list_root_comments(ListRootsQuery(page=1)).pages
    urls = [
        _url_entry(seo.with_lang("/", seo.DEFAULT_LANG, page=page), None, "/", page=page)
        for page in range(1, total_pages + 1)
    ]
    return _urlset(urls)


@require_GET
@cache_page(3600)
def sitemap_threads(request: HttpRequest, number: int) -> HttpResponse:
    # Oldest first, so existing files stay stable and new threads land in the last one.
    page = container().list_root_comments(
        ListRootsQuery(
            ordering=Ordering(SortField.CREATED_AT, SortDirection.ASC), page=number, page_size=SITEMAP_PAGE_SIZE
        )
    )
    if number > page.pages:
        return HttpResponse(status=404)
    urls = []
    for comment in page.items:
        assert comment.id is not None
        lastmod = comment.created_at.date().isoformat() if comment.created_at else None
        urls.append(_url_entry(seo.thread_path(comment.id), lastmod, seo.thread_path(comment.id)))
    return _urlset(urls)


def _url_entry(path: str, lastmod: str | None, alt_path: str, **params: Any) -> str:
    alternates = "".join(
        f'<xhtml:link rel="alternate" hreflang="{alt["hreflang"]}" href="{escape(alt["href"])}"/>'
        for alt in _alternates(alt_path, **params)
    )
    mod = f"<lastmod>{lastmod}</lastmod>" if lastmod else ""
    return f"<url><loc>{escape(seo.absolute(path))}</loc>{mod}{alternates}</url>"


def _urlset(urls: list[str]) -> HttpResponse:
    return _xml(
        '<?xml version="1.0" encoding="UTF-8"?>\n'
        '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9" xmlns:xhtml="http://www.w3.org/1999/xhtml">'
        + "".join(urls)
        + "</urlset>"
    )


def _xml(body: str) -> HttpResponse:
    response = HttpResponse(body, content_type="application/xml; charset=utf-8")
    response["Cache-Control"] = "public, max-age=3600"
    return response
