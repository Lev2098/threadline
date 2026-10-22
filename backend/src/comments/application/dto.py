from __future__ import annotations

import math
from dataclasses import dataclass, field

from comments.domain.attachment import Upload
from comments.domain.values import ClientFingerprint, Ordering

PAGE_SIZE = 25


@dataclass(frozen=True, slots=True)
class PostCommentCommand:
    username: str
    email: str
    text: str
    captcha_key: str
    captcha_answer: str
    fingerprint: ClientFingerprint
    home_page: str | None = None
    parent_id: int | None = None
    upload: Upload | None = None


@dataclass(frozen=True, slots=True)
class ListRootsQuery:
    ordering: Ordering = field(default_factory=Ordering)
    page: int = 1
    page_size: int = PAGE_SIZE


@dataclass(frozen=True, slots=True)
class Page[T]:
    items: list[T]
    page: int
    page_size: int
    total: int

    @property
    def pages(self) -> int:
        return max(1, math.ceil(self.total / self.page_size))


@dataclass(frozen=True, slots=True)
class ThreadSlice[T]:
    items: list[T]
    next_cursor: str | None


@dataclass(frozen=True, slots=True)
class Captcha:
    key: str
    image_png: bytes
    ttl_seconds: int
