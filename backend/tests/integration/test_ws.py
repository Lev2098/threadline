from __future__ import annotations

from typing import Any

import pytest
from asgiref.sync import async_to_sync, sync_to_async
from channels.testing import WebsocketCommunicator
from django.core.cache import cache

from comments.adapters.inbound.rest.auth import issue_token
from comments.application.dto import PostCommentCommand
from comments.bootstrap import container
from comments.domain.values import ClientFingerprint
from config.asgi import application

pytestmark = [pytest.mark.django_db(transaction=True), pytest.mark.integration]
ORIGIN = [(b"origin", b"http://localhost")]


def _post(text: str) -> None:
    captcha = container().issue_captcha()
    container().post_comment(
        PostCommentCommand(
            username="Live",
            email="live@example.com",
            text=text,
            captcha_key=captcha.key,
            captcha_answer="AAAAAA",
            fingerprint=ClientFingerprint("ws-test", "127.0.0.1", "pytest"),
        )
    )


def test_new_comment_is_pushed_to_websocket(monkeypatch: pytest.MonkeyPatch, settings: Any) -> None:
    monkeypatch.setattr("comments.application.use_cases.secrets.choice", lambda alphabet: "A")
    cache.clear()
    token, _, _ = issue_token()

    async def scenario() -> dict[str, Any]:
        ws = WebsocketCommunicator(application, f"/ws/comments/?token={token}", headers=ORIGIN)
        connected, _ = await ws.connect()
        assert connected
        await sync_to_async(_post)("Live <strong>update</strong>")
        message = await ws.receive_json_from(timeout=5)
        await ws.disconnect()
        return message

    message = async_to_sync(scenario)()
    assert message["type"] == "comment.posted"
    assert message["comment"]["html"] == "Live <strong>update</strong>"


def test_websocket_rejects_missing_token() -> None:
    # Accepted, then closed with 4401, so the browser sees the code and can
    # refresh its token (a pre-accept close would surface only as 1006).
    async def scenario() -> dict[str, Any]:
        ws = WebsocketCommunicator(application, "/ws/comments/", headers=ORIGIN)
        await ws.connect()
        return await ws.receive_output(timeout=2)

    message = async_to_sync(scenario)()
    assert message == {"type": "websocket.close", "code": 4401}
