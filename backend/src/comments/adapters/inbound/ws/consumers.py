from __future__ import annotations

import json
from typing import Any
from urllib.parse import parse_qs

from channels.generic.websocket import AsyncJsonWebsocketConsumer
from rest_framework.exceptions import AuthenticationFailed

from comments.adapters.inbound.rest.auth import decode_token
from comments.adapters.outbound.realtime.broadcaster import GROUP

CLOSE_UNAUTHORIZED = 4401


class CommentsConsumer(AsyncJsonWebsocketConsumer):
    """Live feed of new comments. The JWT goes in the query string because
    browsers can't set headers on a WebSocket handshake."""

    async def connect(self) -> None:
        query = parse_qs(self.scope.get("query_string", b"").decode())
        try:
            self.principal = decode_token((query.get("token") or [""])[0])
        except AuthenticationFailed:
            # Accept first: a close before accept becomes HTTP 403 and the browser
            # only sees code 1006, so it could never tell "token expired" apart.
            await self.accept()
            await self.close(code=CLOSE_UNAUTHORIZED)
            return
        await self.channel_layer.group_add(GROUP, self.channel_name)
        await self.accept()

    async def disconnect(self, code: int) -> None:
        await self.channel_layer.group_discard(GROUP, self.channel_name)

    async def receive_json(self, content: Any, **kwargs: Any) -> None:
        if isinstance(content, dict) and content.get("type") == "ping":
            await self.send_json({"type": "pong"})

    async def comment_posted(self, event: dict[str, Any]) -> None:
        await self.send_json({"type": "comment.posted", "comment": event["comment"]})

    @classmethod
    async def encode_json(cls, content: Any) -> str:
        return json.dumps(content, ensure_ascii=False, separators=(",", ":"))
