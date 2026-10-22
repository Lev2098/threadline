from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class CommentPosted:
    """Raised after a comment is persisted.

    Carries ids only: consumers run asynchronously and must read fresh state,
    not a snapshot that might be stale by the time they run.
    """

    comment_id: int
    root_id: int
    parent_id: int | None

    @property
    def is_root(self) -> bool:
        return self.parent_id is None
