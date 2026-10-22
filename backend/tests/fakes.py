"""In-memory adapters: the application core is tested without Django or Redis."""

from __future__ import annotations

from collections.abc import Callable, Iterator, Sequence
from contextlib import contextmanager
from dataclasses import replace
from datetime import UTC, datetime, timedelta

from comments.application.ports import ProcessedImage
from comments.domain.attachment import ImageFormat
from comments.domain.comment import Comment, child_path
from comments.domain.events import CommentPosted
from comments.domain.values import Ordering, SortDirection, SortField


class InMemoryCommentRepository:
    def __init__(self) -> None:
        self.rows: dict[int, Comment] = {}
        self._clock = datetime(2026, 1, 1, tzinfo=UTC)

    def add(self, comment: Comment) -> Comment:
        new_id = len(self.rows) + 1
        parent = self.rows.get(comment.parent_id) if comment.parent_id else None
        self._clock += timedelta(seconds=1)
        saved = replace(
            comment,
            id=new_id,
            root_id=parent.root_id if parent else new_id,
            path=child_path(parent.path if parent else "", new_id),
            created_at=self._clock,
        )
        self.rows[new_id] = saved
        if parent and parent.root_id:
            root = self.rows[parent.root_id]
            self.rows[root.id] = replace(root, replies_count=root.replies_count + 1)  # type: ignore[index]
        return saved

    def get(self, comment_id: int) -> Comment | None:
        return self.rows.get(comment_id)

    def get_many(self, ids: Sequence[int]) -> list[Comment]:
        return [self.rows[i] for i in ids if i in self.rows]

    def list_roots(self, ordering: Ordering, offset: int, limit: int) -> list[Comment]:
        key: Callable[[Comment], object] = {
            SortField.CREATED_AT: lambda c: (c.created_at, c.id),
            SortField.USERNAME: lambda c: (c.author.username.value.lower(), c.id),
            SortField.EMAIL: lambda c: (c.author.email.value.lower(), c.id),
        }[ordering.field]
        roots = sorted(
            (c for c in self.rows.values() if c.is_root),
            key=key,
            reverse=ordering.direction is SortDirection.DESC,
        )
        return roots[offset : offset + limit]

    def count_roots(self) -> int:
        return sum(1 for c in self.rows.values() if c.is_root)

    def thread(self, root_id: int, after_path: str | None, limit: int) -> list[Comment]:
        replies = sorted(
            (c for c in self.rows.values() if c.root_id == root_id and not c.is_root),
            key=lambda c: c.path,
        )
        if after_path:
            replies = [c for c in replies if c.path > after_path]
        return replies[:limit]


class FakeTransactions:
    def __init__(self) -> None:
        self._callbacks: list[Callable[[], None]] = []

    @contextmanager
    def atomic(self) -> Iterator[None]:
        yield
        callbacks, self._callbacks = self._callbacks, []
        for callback in callbacks:
            callback()

    def on_commit(self, callback: Callable[[], None]) -> None:
        self._callbacks.append(callback)


class RecordingPublisher:
    def __init__(self) -> None:
        self.events: list[CommentPosted] = []

    def publish(self, event: CommentPosted) -> None:
        self.events.append(event)


class DictCaptchaStore:
    def __init__(self) -> None:
        self.data: dict[str, str] = {}

    def save(self, key: str, answer: str, ttl_seconds: int) -> None:
        self.data[key] = answer

    def pop(self, key: str) -> str | None:
        return self.data.pop(key, None)


class StubCaptchaRenderer:
    def render(self, text: str) -> bytes:
        return b"\x89PNG" + text.encode()


class StubImageProcessor:
    def __init__(self) -> None:
        self.calls: list[tuple[int, int]] = []

    def fit(self, content: bytes, max_width: int, max_height: int) -> ProcessedImage:
        self.calls.append((max_width, max_height))
        return ProcessedImage(content=content, width=max_width, height=max_height, format=ImageFormat.PNG)


class DictStorage:
    def __init__(self) -> None:
        self.files: dict[str, bytes] = {}

    def save(self, name: str, content: bytes) -> str:
        path = f"attachments/{name}"
        self.files[path] = content
        return path


class IdentitySanitizer:
    def clean(self, html: str) -> str:
        return html


class InMemorySearchIndex:
    def __init__(self) -> None:
        self.docs: dict[int, str] = {}

    def index(self, comment: Comment) -> None:
        assert comment.id is not None
        self.docs[comment.id] = comment.text.plain.lower()

    def search(self, query: str, offset: int, limit: int) -> tuple[list[int], int]:
        hits = [i for i, text in sorted(self.docs.items(), reverse=True) if query.lower() in text]
        return hits[offset : offset + limit], len(hits)


class RecordingBroadcaster:
    def __init__(self) -> None:
        self.sent: list[Comment] = []

    def comment_posted(self, comment: Comment) -> None:
        self.sent.append(comment)
