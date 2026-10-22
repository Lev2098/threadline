"""End-to-end through the REST adapter, real ORM and real cache.

Run locally on SQLite, in docker compose on PostgreSQL + Redis.
"""

from __future__ import annotations

import io
from collections.abc import Iterator
from typing import Any

import pytest
from django.core.cache import cache
from PIL import Image
from rest_framework.test import APIClient

from comments.bootstrap import container

pytestmark = [pytest.mark.django_db(transaction=True), pytest.mark.integration]


@pytest.fixture(autouse=True)
def _isolate(settings: Any, tmp_path: Any, monkeypatch: pytest.MonkeyPatch) -> Iterator[None]:
    settings.MEDIA_ROOT = str(tmp_path)
    settings.REST_FRAMEWORK = {**settings.REST_FRAMEWORK, "DEFAULT_THROTTLE_CLASSES": []}
    # Deterministic captcha: every character is "A".
    monkeypatch.setattr("comments.application.use_cases.secrets.choice", lambda alphabet: "A")
    cache.clear()
    yield
    cache.clear()


@pytest.fixture
def client() -> APIClient:
    api = APIClient()
    token = api.post("/api/v1/session").json()["token"]
    api.credentials(HTTP_AUTHORIZATION=f"Bearer {token}")
    return api


def post_comment(client: APIClient, **fields: Any) -> Any:
    captcha = client.get("/api/v1/captcha").json()
    data = {
        "username": "Anonym",
        "email": "anon@example.com",
        "text": "Hello <i>world</i>",
        "captcha_key": captcha["key"],
        "captcha": "aaaaaa",
        **fields,
    }
    return client.post("/api/v1/comments", data, format="multipart")


def png(width: int, height: int) -> io.BytesIO:
    buffer = io.BytesIO()
    Image.new("RGB", (width, height), (120, 80, 200)).save(buffer, "PNG")
    buffer.seek(0)
    buffer.name = "big.png"
    return buffer


def test_post_requires_token() -> None:
    response = APIClient().post("/api/v1/comments", {}, format="multipart")
    assert response.status_code in (401, 403)


def test_captcha_returns_png(client: APIClient) -> None:
    body = client.get("/api/v1/captcha").json()
    assert body["image"].startswith("data:image/png;base64,") and body["key"]


def test_full_flow_post_list_thread(client: APIClient) -> None:
    root = post_comment(client)
    assert root.status_code == 201, root.json()
    root_id = root.json()["id"]

    reply = post_comment(client, parent_id=root_id, username="Rum8", text="Reply")
    nested = post_comment(client, parent_id=reply.json()["id"], text="Nested <code>x</code>")
    assert nested.json()["depth"] == 2

    listing = client.get("/api/v1/comments").json()
    assert listing["total"] == 1
    assert listing["items"][0]["replies_count"] == 2  # cache invalidated after replies

    thread = client.get(f"/api/v1/comments/{root_id}/thread").json()
    assert [c["username"] for c in thread["items"]] == ["Rum8", "Anonym"]
    assert thread["next_cursor"] is None


def test_validation_errors_are_per_field(client: APIClient) -> None:
    response = post_comment(client, username="bad name!", email="x", text="<script>alert(1)</script>")
    assert response.status_code == 400
    assert set(response.json()["errors"]) == {"username", "email", "text"}


def test_wrong_captcha(client: APIClient) -> None:
    response = post_comment(client, captcha="zzzzzz")
    assert response.status_code == 400
    assert response.json()["code"] == "invalid_captcha"


def test_sorting_and_pagination(client: APIClient) -> None:
    for name in ["Bravo", "alpha", "Charlie"]:
        assert post_comment(client, username=name).status_code == 201

    default = client.get("/api/v1/comments").json()["items"]
    assert [c["username"] for c in default] == ["Charlie", "alpha", "Bravo"]  # LIFO

    by_name = client.get("/api/v1/comments", {"ordering": "username"}).json()["items"]
    assert [c["username"] for c in by_name] == ["alpha", "Bravo", "Charlie"]

    bad = client.get("/api/v1/comments", {"ordering": "id; DROP TABLE comments"})
    assert bad.status_code == 400


def test_image_is_downscaled(client: APIClient) -> None:
    response = post_comment(client, attachment=png(1280, 960))
    assert response.status_code == 201, response.json()
    attachment = response.json()["attachment"]
    assert (attachment["width"], attachment["height"]) == (320, 240)


def test_fake_image_rejected(client: APIClient) -> None:
    fake = io.BytesIO(b"<?php system($_GET['c']); ?>")
    fake.name = "shell.png"
    response = post_comment(client, attachment=fake)
    assert response.status_code == 400
    assert "attachment" in response.json()["errors"]


def test_preview_and_graphql(client: APIClient) -> None:
    preview = client.post("/api/v1/comments/preview", {"text": "<strong>b</strong> & c"}, format="json")
    assert preview.json()["html"] == "<strong>b</strong> &amp; c"

    post_comment(client, text="Searchable elephant")
    gql = client.post(
        "/graphql",
        {"query": '{ comments(page: 1) { total items { username html } } search(q: "elephant") { total } }'},
        format="json",
    ).json()
    assert gql["data"]["comments"]["total"] == 1
    assert gql["data"]["search"]["total"] == 1


def test_container_is_singleton() -> None:
    assert container() is container()
