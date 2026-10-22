"""Read-through cache as a decorator around any ``CommentRepository``.

Use cases don't know caching exists; it is plugged in by the composition root.

Invalidation uses version counters instead of deleting keys: bumping
``roots:ver`` makes every cached root page unreachable in O(1), and the old
entries simply expire. Versions are bumped on transaction commit, never
before, so a concurrent reader can't re-cache pre-commit data under the new
version.
"""

from __future__ import annotations

from collections.abc import Sequence

from django.core.cache import BaseCache

from comments.application.ports import CommentRepository, TransactionManager
from comments.domain.comment import Comment
from comments.domain.values import Ordering

ROOTS_TTL = 300
COUNT_TTL = 300
THREAD_TTL = 600
# Only the first pages are hot; deep pages are cheap enough and rarely repeat.
CACHED_ROOT_PAGES = 10


class CachedCommentRepository:
    def __init__(self, inner: CommentRepository, cache: BaseCache, transactions: TransactionManager) -> None:
        self._inner = inner
        self._cache = cache
        self._tx = transactions

    def add(self, comment: Comment) -> Comment:
        saved = self._inner.add(comment)
        root_id = saved.root_id
        self._tx.on_commit(lambda: self._invalidate(root_id))
        return saved

    def get(self, comment_id: int) -> Comment | None:
        return self._inner.get(comment_id)

    def get_many(self, ids: Sequence[int]) -> list[Comment]:
        return self._inner.get_many(ids)

    def list_roots(self, ordering: Ordering, offset: int, limit: int) -> list[Comment]:
        if offset >= CACHED_ROOT_PAGES * limit:
            return self._inner.list_roots(ordering, offset, limit)
        key = f"roots:v{self._version('roots:ver')}:{ordering}:{offset}:{limit}"
        cached: list[Comment] | None = self._cache.get(key)
        if cached is None:
            cached = self._inner.list_roots(ordering, offset, limit)
            self._cache.set(key, cached, ROOTS_TTL)
        return cached

    def count_roots(self) -> int:
        key = f"roots:count:v{self._version('roots:ver')}"
        cached: int | None = self._cache.get(key)
        if cached is None:
            cached = self._inner.count_roots()
            self._cache.set(key, cached, COUNT_TTL)
        return cached

    def thread(self, root_id: int, after_path: str | None, limit: int) -> list[Comment]:
        key = f"thread:{root_id}:v{self._version(f'thread:{root_id}:ver')}:{after_path or ''}:{limit}"
        cached: list[Comment] | None = self._cache.get(key)
        if cached is None:
            cached = self._inner.thread(root_id, after_path, limit)
            self._cache.set(key, cached, THREAD_TTL)
        return cached

    def _version(self, key: str) -> int:
        version: int | None = self._cache.get(key)
        if version is None:
            self._cache.add(key, 1, timeout=None)
            version = self._cache.get(key) or 1
        return version

    def _invalidate(self, root_id: int | None) -> None:
        # Root rows show replies_count, so any new comment changes the root list.
        self._bump("roots:ver")
        if root_id is not None:
            self._bump(f"thread:{root_id}:ver")

    def _bump(self, key: str) -> None:
        try:
            self._cache.incr(key)
        except ValueError:  # key missing or evicted
            self._cache.set(key, 2, timeout=None)
