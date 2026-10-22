from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import datetime

from comments.domain.attachment import Attachment
from comments.domain.markup import CommentText
from comments.domain.values import Author, ClientFingerprint

PATH_SEGMENT_WIDTH = 10
PATH_SEPARATOR = "."
# Deeper replies would hit PostgreSQL's btree row limit on the path index
# (~370 levels) long before that; 100 keeps paths short and threads readable.
MAX_DEPTH = 100
_PATH_RE = re.compile(r"[0-9]{10}(?:\.[0-9]{10})*")


def is_valid_path(path: str) -> bool:
    return bool(_PATH_RE.fullmatch(path)) and path.count(PATH_SEPARATOR) <= MAX_DEPTH


def child_path(parent_path: str, comment_id: int) -> str:
    """Materialized path: fixed-width ids joined by dots.

    Lexicographic order of paths equals depth-first, chronological order of
    the thread, so a whole thread is one ``ORDER BY path`` range scan.
    """
    segment = str(comment_id).zfill(PATH_SEGMENT_WIDTH)
    if len(segment) > PATH_SEGMENT_WIDTH:
        # Lexicographic order would break; widen the segment with a data migration first.
        raise OverflowError(f"comment id {comment_id} exceeds the path segment width")
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
