from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime

from comments.domain.attachment import Attachment
from comments.domain.markup import CommentText
from comments.domain.values import Author, ClientFingerprint

PATH_SEGMENT_WIDTH = 10
PATH_SEPARATOR = "."


def child_path(parent_path: str, comment_id: int) -> str:
    """Materialized path: fixed-width ids joined by dots.

    Lexicographic order of paths equals depth-first, chronological order of
    the thread, so a whole thread is one ``ORDER BY path`` range scan.
    """
    segment = str(comment_id).zfill(PATH_SEGMENT_WIDTH)
    return f"{parent_path}{PATH_SEPARATOR}{segment}" if parent_path else segment


@dataclass(slots=True)
class Comment:
    author: Author
    text: CommentText
    fingerprint: ClientFingerprint
    parent_id: int | None = None
    attachment: Attachment | None = None
    id: int | None = None
    root_id: int | None = None
    path: str = ""
    created_at: datetime | None = None
    replies_count: int = 0

    @property
    def is_root(self) -> bool:
        return self.parent_id is None

    @property
    def depth(self) -> int:
        return self.path.count(PATH_SEPARATOR) if self.path else 0
