"""Anonymous client identity via JWT.

The brief has no registration, yet comments must be tied to "data that helps
identify the client". On first visit the SPA requests a signed token with a
random client id; it is sent with every write and with the WebSocket handshake.
This gives per-client rate limits and attribution without accounts.
"""

from __future__ import annotations

import time
import uuid
from dataclasses import dataclass
from typing import Any

import jwt
from django.conf import settings
from rest_framework.authentication import BaseAuthentication, get_authorization_header
from rest_framework.exceptions import AuthenticationFailed
from rest_framework.permissions import BasePermission
from rest_framework.request import Request

ALGORITHM = "HS256"
ISSUER = "dzen-comments"


@dataclass(frozen=True)
class ClientPrincipal:
    client_id: str
    is_authenticated: bool = True

    @property
    def pk(self) -> str:  # used by DRF throttles as the rate-limit key
        return self.client_id


def issue_token(client_id: str | None = None) -> tuple[str, str, int]:
    client_id = client_id or uuid.uuid4().hex
    now = int(time.time())
    ttl = settings.JWT_TTL_SECONDS
    token = jwt.encode(
        {"sub": client_id, "iat": now, "exp": now + ttl, "iss": ISSUER, "typ": "client"},
        settings.JWT_SECRET,
        algorithm=ALGORITHM,
    )
    return token, client_id, ttl


def decode_token(token: str) -> ClientPrincipal:
    try:
        claims: dict[str, Any] = jwt.decode(
            token,
            settings.JWT_SECRET,
            algorithms=[ALGORITHM],  # pinned: never trust the token's own "alg"
            issuer=ISSUER,
            options={"require": ["sub", "exp", "iat"]},
        )
    except jwt.PyJWTError as exc:
        raise AuthenticationFailed("Invalid or expired session token.") from exc
    if claims.get("typ") != "client":
        raise AuthenticationFailed("Invalid session token type.")
    return ClientPrincipal(client_id=str(claims["sub"]))


class JWTClientAuthentication(BaseAuthentication):
    keyword = b"bearer"

    def authenticate(self, request: Request) -> tuple[ClientPrincipal, str] | None:
        parts = get_authorization_header(request).split()
        if not parts or parts[0].lower() != self.keyword:
            return None
        if len(parts) != 2:
            raise AuthenticationFailed("Malformed Authorization header.")
        try:
            token = parts[1].decode("ascii")
        except UnicodeDecodeError as exc:
            raise AuthenticationFailed("Malformed Authorization header.") from exc
        return decode_token(token), token

    def authenticate_header(self, request: Request) -> str:
        return 'Bearer realm="comments"'


class HasClientToken(BasePermission):
    message = "A session token is required. Call POST /api/v1/session first."

    def has_permission(self, request: Request, view: Any) -> bool:
        return isinstance(request.user, ClientPrincipal)
