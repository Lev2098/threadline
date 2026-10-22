"""ASGI entry point of the ``realtime`` service: WebSockets only.

Plain HTTP is served by gunicorn (``config.wsgi``). Here HTTP answers just the
container healthcheck; every other path is 404, so the WebSocket replicas
don't expose a second copy of the API, the admin or GraphQL.
"""

import os
from typing import Any

from django.core.asgi import get_asgi_application

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings")
get_asgi_application()  # sets Django up; must run before importing consumers

from channels.routing import ProtocolTypeRouter, URLRouter  # noqa: E402
from channels.security.websocket import AllowedHostsOriginValidator  # noqa: E402
from django.urls import path  # noqa: E402

from comments.adapters.inbound.ws.consumers import CommentsConsumer  # noqa: E402


async def http_health_only(scope: dict[str, Any], receive: Any, send: Any) -> None:
    ok = scope.get("path") == "/healthz"
    body = b'{"status": "ok"}' if ok else b'{"code": "not_found", "message": "Not found.", "errors": {}}'
    await send(
        {
            "type": "http.response.start",
            "status": 200 if ok else 404,
            "headers": [(b"content-type", b"application/json"), (b"content-length", str(len(body)).encode())],
        }
    )
    await send({"type": "http.response.body", "body": body})


application = ProtocolTypeRouter(
    {
        "http": http_health_only,
        "websocket": AllowedHostsOriginValidator(URLRouter([path("ws/comments/", CommentsConsumer.as_asgi())])),
    }
)
