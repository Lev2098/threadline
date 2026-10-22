"""Regression tests for QA findings that need the HTTP stack, Pillow or ES."""

from __future__ import annotations

import io
from collections.abc import Iterator
from typing import Any

import pytest
from django.core.cache import cache
from django.test import Client
from elasticsearch import Elasticsearch
from PIL import Image
from rest_framework.test import APIClient

from comments.adapters.outbound.media.images import PillowImageProcessor
from comments.adapters.outbound.sanitizer import Nh3Sanitizer
from comments.adapters.outbound.search.elastic import ElasticsearchSearchIndex
from comments.domain.errors import AttachmentError, ServiceUnavailable
from tests.integration.test_api import post_comment

pytestmark = [pytest.mark.django_db(transaction=True), pytest.mark.integration]


@pytest.fixture(autouse=True)
def _isolate(settings: Any, tmp_path: Any, monkeypatch: pytest.MonkeyPatch) -> Iterator[None]:
    settings.MEDIA_ROOT = str(tmp_path)
    settings.REST_FRAMEWORK = {**settings.REST_FRAMEWORK, "DEFAULT_THROTTLE_CLASSES": []}
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


# --- HTTP ---------------------------------------------------------------------------


def test_non_utf8_authorization_header_is_401_not_500() -> None:
    response = Client().get("/api/v1/captcha", HTTP_AUTHORIZATION=b"Bearer \xff\xfe".decode("latin-1"))
    assert response.status_code == 401
    assert response.json()["code"] == "authentication_failed"


def test_serializer_errors_use_the_documented_shape() -> None:
    body = APIClient().get("/api/v1/comments", {"page": 0}).json()
    assert body["code"] == "invalid" and isinstance(body["errors"]["page"], str)


def test_unknown_api_path_is_json_404(settings: Any) -> None:
    settings.DEBUG = False
    response = Client().get("/api/v1/nope")
    assert response.status_code == 404 and response.json()["code"] == "not_found"


def test_healthz_ignores_host_validation(settings: Any) -> None:
    settings.ALLOWED_HOSTS = ["comments.example.com"]
    assert Client(HTTP_HOST="127.0.0.1").get("/healthz").status_code == 200


def test_cyrillic_captcha_is_400(client: APIClient) -> None:
    response = post_comment(client, captcha="абвгде")
    assert response.status_code == 400 and response.json()["code"] == "invalid_captcha"


def test_graphql_alias_flood_is_refused() -> None:
    aliases = " ".join(f"p{i}: comments(page: {i + 1}) {{ total }}" for i in range(10))
    body = APIClient().post("/graphql", {"query": f"{{ {aliases} }}"}, format="json").json()
    assert body.get("errors") and not body.get("data")


# --- images -------------------------------------------------------------------------


def _png(width: int, height: int, mode: str = "1") -> bytes:
    buffer = io.BytesIO()
    Image.new(mode, (width, height)).save(buffer, "PNG")
    return buffer.getvalue()


def test_image_above_pixel_limit_is_rejected() -> None:
    with pytest.raises(AttachmentError):
        PillowImageProcessor().fit(_png(8000, 8000), 320, 240)  # 64 MP: Pillow alone only warns


def test_gif_with_too_many_frames_is_rejected_before_decoding() -> None:
    frames = [Image.new("P", (2000, 2000), i % 255) for i in range(20)]  # 80 MP in total
    buffer = io.BytesIO()
    frames[0].save(buffer, "GIF", save_all=True, append_images=frames[1:])
    with pytest.raises(AttachmentError):
        PillowImageProcessor().fit(buffer.getvalue(), 320, 240)


def test_mpo_photo_is_accepted_as_jpeg() -> None:
    buffer = io.BytesIO()
    first, second = Image.new("RGB", (800, 600), "red"), Image.new("RGB", (800, 600), "blue")
    first.save(buffer, "MPO", save_all=True, append_images=[second])
    result = PillowImageProcessor().fit(buffer.getvalue(), 320, 240)
    assert result.format == "jpeg" and (result.width, result.height) == (320, 240)


# --- markup and search ----------------------------------------------------------------


def test_sanitizer_output_has_no_undefined_xml_entities() -> None:
    assert Nh3Sanitizer().clean("a" + chr(0xA0) + "b") == "a&#160;b"


def test_search_outage_is_service_unavailable() -> None:
    dead = Elasticsearch("http://127.0.0.1:1", request_timeout=1, max_retries=0)
    with pytest.raises(ServiceUnavailable):
        ElasticsearchSearchIndex(dead, "comments").search("x", 0, 25)
