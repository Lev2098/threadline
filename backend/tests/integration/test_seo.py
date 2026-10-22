"""Server-rendered pages: metadata, structured data, status codes, sitemaps."""

from __future__ import annotations

import json
import re
from collections.abc import Iterator
from typing import Any
from xml.etree import ElementTree

import pytest
from django.core.cache import cache
from django.test import Client
from rest_framework.test import APIClient

from tests.integration.test_api import post_comment

pytestmark = [pytest.mark.django_db(transaction=True), pytest.mark.integration]


@pytest.fixture(autouse=True)
def _isolate(settings: Any, tmp_path: Any, monkeypatch: pytest.MonkeyPatch) -> Iterator[None]:
    settings.MEDIA_ROOT = str(tmp_path)
    settings.SITE_URL = "https://comments.example.com"
    settings.REST_FRAMEWORK = {**settings.REST_FRAMEWORK, "DEFAULT_THROTTLE_CLASSES": []}
    monkeypatch.setattr("comments.application.use_cases.secrets.choice", lambda alphabet: "A")
    cache.clear()
    yield
    cache.clear()


@pytest.fixture
def api() -> APIClient:
    client = APIClient()
    token = client.post("/api/v1/session").json()["token"]
    client.credentials(HTTP_AUTHORIZATION=f"Bearer {token}")
    return client


def json_ld(html: str) -> list[dict[str, Any]]:
    blocks = re.findall(r'<script type="application/ld\+json">(.*?)</script>', html, re.DOTALL)
    return [json.loads(block) for block in blocks]


def test_home_has_seo_head_and_crawlable_links(api: APIClient) -> None:
    root = post_comment(api, text="Перше обговорення про <strong>архітектуру</strong>").json()
    html = Client().get("/").content.decode()

    assert '<html lang="uk"' in html
    assert '<link rel="canonical" href="https://comments.example.com/" />' in html
    assert 'hreflang="ru" href="https://comments.example.com/?lang=ru"' in html
    assert 'hreflang="x-default"' in html
    assert f'href="/t/{root["id"]}"' in html
    assert json_ld(html)[0]["@type"] == "WebSite"
    initial = re.search(r'<script id="tl-initial" type="application/json">(.*?)</script>', html, re.DOTALL)
    assert initial and json.loads(initial.group(1))["page"]["items"][0]["id"] == root["id"]


def test_thread_page_has_discussion_structured_data(api: APIClient) -> None:
    root = post_comment(api, text="Як масштабувати <i>коментарі</i>?").json()
    post_comment(api, parent_id=root["id"], username="Rum8", text="Через індекси")
    response = Client().get(f"/t/{root['id']}?lang=ru")
    html = response.content.decode()

    assert response.status_code == 200 and response["Content-Language"] == "ru"
    assert "<title>Як масштабувати коментарі? — Threadline</title>" in html
    data = json_ld(html)[0]
    assert data["@type"] == "DiscussionForumPosting"
    assert data["interactionStatistic"]["userInteractionCount"] == 1
    assert data["comment"][0]["author"]["name"] == "Rum8"
    assert '<html lang="ru"' in html and f'id="c{root["id"]}"' in html


def test_reply_permalink_redirects_to_its_thread(api: APIClient) -> None:
    root = post_comment(api).json()
    reply = post_comment(api, parent_id=root["id"]).json()
    response = Client().get(f"/t/{reply['id']}")
    assert response.status_code == 301
    assert response["Location"] == f"/t/{root['id']}#c{reply['id']}"


def test_missing_thread_is_a_real_404_with_noindex() -> None:
    response = Client().get("/t/999999")
    assert response.status_code == 404
    assert 'content="noindex,follow"' in response.content.decode()


def test_sorted_view_is_not_indexed_and_past_last_page_redirects(api: APIClient) -> None:
    post_comment(api)
    assert 'content="noindex,follow"' in Client().get("/?ordering=username").content.decode()
    assert Client().get("/?page=50").status_code == 302


def test_user_text_cannot_break_out_of_json_ld(api: APIClient) -> None:
    root = post_comment(api, text="&lt;/script&gt;&lt;script&gt;alert(1)&lt;/script&gt;").json()
    html = Client().get(f"/t/{root['id']}").content.decode()
    ld = re.search(r'<script type="application/ld\+json">(.*?)</script>', html, re.DOTALL)
    assert ld and "</script" not in ld.group(1) and "<script" not in ld.group(1)


def test_robots_and_sitemaps(api: APIClient) -> None:
    roots = [post_comment(api).json()["id"] for _ in range(3)]
    robots = Client().get("/robots.txt").content.decode()
    assert "Disallow: /api/" in robots and "Sitemap: https://comments.example.com/sitemap.xml" in robots

    ns = {"s": "http://www.sitemaps.org/schemas/sitemap/0.9"}
    index = ElementTree.fromstring(Client().get("/sitemap.xml").content)
    locs = [loc.text for loc in index.findall("s:sitemap/s:loc", ns)]
    assert locs == [
        "https://comments.example.com/sitemaps/pages.xml",
        "https://comments.example.com/sitemaps/threads-1.xml",
    ]
    threads = ElementTree.fromstring(Client().get("/sitemaps/threads-1.xml").content)
    urls = [loc.text for loc in threads.findall("s:url/s:loc", ns)]
    assert urls == [f"https://comments.example.com/t/{i}" for i in roots]  # oldest first
    assert Client().get("/sitemaps/threads-2.xml").status_code == 404


def test_comment_detail_endpoint(api: APIClient) -> None:
    root = post_comment(api).json()
    assert APIClient().get(f"/api/v1/comments/{root['id']}").json()["id"] == root["id"]
    assert APIClient().get("/api/v1/comments/999999").status_code == 404
