"""Value objects: validated on construction, immutable afterwards.

Once a ``UserName`` exists it is guaranteed to be valid, so the rest of the
code never re-validates it.
"""

from __future__ import annotations

import ipaddress
import re
from dataclasses import dataclass
from enum import StrEnum
from urllib.parse import urlsplit

from comments.domain.errors import ValidationError

_USERNAME_RE = re.compile(r"^[A-Za-z0-9]+$")
# Pragmatic RFC 5322 subset: local@domain.tld, no quoted local parts.
# Local part: dot-atoms only (no leading, trailing or doubled dots).
_EMAIL_RE = re.compile(
    r"^[A-Za-z0-9!#$%&'*+/=?^_`{|}~-]+(?:\.[A-Za-z0-9!#$%&'*+/=?^_`{|}~-]+)*"
    r"@[A-Za-z0-9](?:[A-Za-z0-9-]{0,61}[A-Za-z0-9])?"
    r"(?:\.[A-Za-z0-9](?:[A-Za-z0-9-]{0,61}[A-Za-z0-9])?)+$"
)
_URL_FORBIDDEN_RE = re.compile(r"[\s<>\"'`\\]")
_LABEL_RE = re.compile(r"^[A-Za-z0-9](?:[A-Za-z0-9-]{0,61}[A-Za-z0-9])?$")

USERNAME_MAX = 64
EMAIL_MAX = 254
URL_MAX = 2048


@dataclass(frozen=True, slots=True)
class UserName:
    value: str

    def __post_init__(self) -> None:
        if not self.value:
            raise ValidationError("User name is required.", field="username")
        if len(self.value) > USERNAME_MAX:
            raise ValidationError(f"User name must be at most {USERNAME_MAX} characters.", field="username")
        if not _USERNAME_RE.fullmatch(self.value):
            raise ValidationError("User name may contain only Latin letters and digits.", field="username")

    def __str__(self) -> str:
        return self.value


@dataclass(frozen=True, slots=True)
class Email:
    value: str

    def __post_init__(self) -> None:
        if not self.value:
            raise ValidationError("E-mail is required.", field="email")
        if len(self.value) > EMAIL_MAX or not _EMAIL_RE.fullmatch(self.value):
            raise ValidationError("Enter a valid e-mail address.", field="email")

    @classmethod
    def normalized(cls, raw: str) -> Email:
        # Domain part is case-insensitive by RFC; local part is kept as typed.
        raw = raw.strip()
        local, sep, domain = raw.rpartition("@")
        return cls(f"{local}{sep}{domain.lower()}" if sep else raw)

    def __str__(self) -> str:
        return self.value


@dataclass(frozen=True, slots=True)
class HomePage:
    value: str

    def __post_init__(self) -> None:
        if len(self.value) > URL_MAX or not _is_web_url(self.value):
            raise ValidationError("Home page must be a valid http(s) URL.", field="home_page")

    @classmethod
    def optional(cls, raw: str | None) -> HomePage | None:
        raw = (raw or "").strip()
        return cls(raw) if raw else None

    def __str__(self) -> str:
        return self.value


def _is_web_url(value: str) -> bool:
    """http(s) URL with a real host: domain (IDN allowed), IPv4/IPv6 or localhost."""
    if _URL_FORBIDDEN_RE.search(value):
        return False
    try:
        parts = urlsplit(value)
        port = parts.port  # raises ValueError when out of range
    except ValueError:
        return False
    host = parts.hostname or ""
    if parts.scheme.lower() not in {"http", "https"} or not host or parts.username or parts.password:
        return False
    if port == 0:
        return False
    try:
        ipaddress.ip_address(host)
        return True
    except ValueError:
        pass
    if host == "localhost":
        return True
    try:
        ascii_host = host.encode("idna").decode("ascii")
    except UnicodeError:
        return False
    labels = ascii_host.rstrip(".").split(".")
    return len(labels) >= 2 and all(_LABEL_RE.fullmatch(label) for label in labels) and not labels[-1].isdigit()


def restore[T](cls: type[T], value: str) -> T:
    """Rebuild a value object from trusted storage without re-validating.

    Rules may tighten over time; rows stored under old rules must still load
    instead of breaking every page that contains them.
    """
    obj = object.__new__(cls)
    object.__setattr__(obj, "value", value)
    return obj


@dataclass(frozen=True, slots=True)
class Author:
    username: UserName
    email: Email
    home_page: HomePage | None = None


@dataclass(frozen=True, slots=True)
class ClientFingerprint:
    """Data that helps identify the client behind a comment (see brief)."""

    client_id: str
    ip: str | None
    user_agent: str


class SortField(StrEnum):
    CREATED_AT = "created_at"
    USERNAME = "username"
    EMAIL = "email"


class SortDirection(StrEnum):
    ASC = "asc"
    DESC = "desc"


@dataclass(frozen=True, slots=True)
class Ordering:
    field: SortField = SortField.CREATED_AT
    direction: SortDirection = SortDirection.DESC  # LIFO by default

    @classmethod
    def parse(cls, raw: str | None) -> Ordering:
        """Parse ``"-created_at"`` / ``"username"`` style strings.

        Unknown values fall back to the default instead of failing: sorting is
        a presentation concern and must never be a vector for injection.
        """
        raw = (raw or "").strip()
        direction = SortDirection.DESC if raw.startswith("-") else SortDirection.ASC
        try:
            return cls(SortField(raw.lstrip("-")), direction)
        except ValueError:
            return cls()

    def __str__(self) -> str:
        return f"{'-' if self.direction is SortDirection.DESC else ''}{self.field.value}"
