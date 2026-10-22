"""Ports: what the application needs from the outside world.

Declared as ``Protocol`` so adapters satisfy them structurally, without
inheriting from anything in the core. Each port is small and named after the
capability, not after the technology behind it.
"""

from __future__ import annotations

from collections.abc import Callable, Sequence
from contextlib import AbstractContextManager
from dataclasses import dataclass
from typing import Protocol

from comments.domain.attachment import ImageFormat
from comments.domain.comment import Comment
from comments.domain.events import CommentPosted
from comments.domain.values import Ordering


class CommentRepository(Protocol):
    def add(self, comment: Comment) -> Comment:
        """Persist a new comment, assigning id, root_id, path and created_at."""

    def get(self, comment_id: int) -> Comment | None: ...

    def get_many(self, ids: Sequence[int]) -> list[Comment]:
        """Return comments in the order of ``ids``, skipping missing ones."""

    def list_roots(self, ordering: Ordering, offset: int, limit: int) -> list[Comment]: ...

    def count_roots(self) -> int: ...

    def thread(self, root_id: int, after_path: str | None, limit: int) -> list[Comment]:
        """Replies of a root comment in depth-first order, keyset-paginated."""


class TransactionManager(Protocol):
    def atomic(self) -> AbstractContextManager[None]: ...

    def on_commit(self, callback: Callable[[], None]) -> None: ...


class EventPublisher(Protocol):
    def publish(self, event: CommentPosted) -> None:
        """Deliver the event once the current transaction commits."""


class CaptchaStore(Protocol):
    def save(self, key: str, answer: str, ttl_seconds: int) -> None: ...

    def pop(self, key: str) -> str | None:
        """Return and delete the answer atomically: a captcha is single-use."""


class CaptchaRenderer(Protocol):
    def render(self, text: str) -> bytes:
        """Return a PNG image of the distorted text."""


@dataclass(frozen=True, slots=True)
class ProcessedImage:
    content: bytes
    width: int
    height: int
    format: ImageFormat


class ImageProcessor(Protocol):
    def fit(self, content: bytes, max_width: int, max_height: int) -> ProcessedImage:
        """Downscale proportionally to fit the box; never upscale."""


class FileStorage(Protocol):
    def save(self, name: str, content: bytes) -> str:
        """Store the file and return its storage path."""


class HtmlSanitizer(Protocol):
    def clean(self, html: str) -> str:
        """Second line of defense applied to already-validated markup."""


class SearchIndex(Protocol):
    def index(self, comment: Comment) -> None: ...

    def search(self, query: str, offset: int, limit: int) -> tuple[list[int], int]:
        """Return matching comment ids (best first) and the total hit count."""


class Broadcaster(Protocol):
    def comment_posted(self, comment: Comment) -> None:
        """Push the new comment to connected clients."""
