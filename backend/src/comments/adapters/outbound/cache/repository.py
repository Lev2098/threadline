"""Read-through cache as a decorator around any ``CommentRepository``.

Use cases don't know caching exists; it is plugged in by the composition root.

What is cached is what is expensive:

* root pages cache only the *ids* of the page (the ORDER BY ... OFFSET scan);
  rows are re-read by primary key on every hit, which is cheap and keeps
  ``replies_count`` exact. So replies never invalidate the root list, only a
  new root does. (The first load test showed why: with ~10 writes/s, flushing
  page 1 on every reply made the cache useless and PostgreSQL CPU-bound.)
* the root count is kept with INCR instead of re-running COUNT(*);
* the first slice of each thread (no cursor) is cached whole and invalidated
  per root. Cursor slices are not cached: arbitrary cursors would let anyone
  fill Redis with unique keys and evict captchas and throttle counters.

Invalidation uses version counters instead of deleting keys: bumping a
version makes all dependent entries unreachable in O(1), and they expire on
their own. Versions are bumped after commit, never before, so a concurrent
reader can't re-cache pre-commit data under the new version. A missing version
(expired or evicted) restarts from the current time in ms, never from 1, so it
can't collide with entries cached under an older version.
"""

from __future__ import annotations

import time
from collections.abc import Sequence
from contextlib import suppress

from django.core.cache import BaseCache

from comments.application.ports import CommentRepository, TransactionManager
from comments.domain.comment import Comment
from comments.domain.values import Ordering

ROOTS_TTL = 300
# A reader recomputing the count can race a commit and miss one row; the short
# TTL bounds that drift to a minute.
COUNT_TTL = 60
VERSION_TTL = 86_400
THREAD_TTL = 600
# Only the first pages are hot; deep pages are cheap enough and rarely repeat.
CACHED_ROOT_PAGES = 10
ROOTS_COUNT_KEY = "roots:count"


class CachedCommentRepository:
    def __init__(self, inner: CommentRepository, cache: BaseCache, transactions: TransactionManager) -> None:
        self._inner = inner
        self._cache = cache
        self._tx = transactions

    def add(self, comment: Comment) -> Comment:
        saved = self._inner.add(comment)
        root_id, is_root = saved.root_id, saved.is_root
        self._tx.on_commit(lambda: self._invalidate(root_id, is_root))
        return saved

    def get(self, comment_id: int) -> Comment | None:
        return self._inner.get(comment_id)

    def get_many(self, ids: Sequence[int]) -> list[Comment]:
        return self._inner.get_many(ids)

    def list_roots(self, ordering: Ordering, offset: int, limit: int) -> list[Comment]:
        if offset >= CACHED_ROOT_PAGES * limit:
            return self._inner.list_roots(ordering, offset, limit)
        key = f"roots:v{self._version('roots:ver')}:{ordering}:{offset}:{limit}"
        ids: list[int] | None = self._cache.get(key)
        if ids is None:
            page = self._inner.list_roots(ordering, offset, limit)
            self._cache.set(key, [c.id for c in page], ROOTS_TTL)
            return page
        return self._inner.get_many(ids)

    def count_roots(self) -> int:
        cached: int | None = self._cache.get(ROOTS_COUNT_KEY)
        if cached is None:
            cached = self._inner.count_roots()
            self._cache.add(ROOTS_COUNT_KEY, cached, COUNT_TTL)
        return cached

    def thread(self, root_id: int, after_path: str | None, limit: int) -> list[Comment]:
        if after_path:
            return self._inner.thread(root_id, after_path, limit)
        key = f"thread:{root_id}:v{self._version(f'thread:{root_id}:ver')}:{after_path or ''}:{limit}"
        cached: list[Comment] | None = self._cache.get(key)
        if cached is None:
            cached = self._inner.thread(root_id, after_path, limit)
            self._cache.set(key, cached, THREAD_TTL)
        return cached

    def _version(self, key: str) -> int:
        version: int | None = self._cache.get(key)
        if version is None:
            fresh = time.time_ns() // 1_000_000
            self._cache.add(key, fresh, VERSION_TTL)
            version = self._cache.get(key) or fresh
        return version

    def _invalidate(self, root_id: int | None, is_root: bool) -> None:
        if is_root:
            self._bump("roots:ver")
            # Missing key: the next read computes it (see COUNT_TTL).
            with suppress(ValueError):
                self._cache.incr(ROOTS_COUNT_KEY)
        elif root_id is not None:
            self._bump(f"thread:{root_id}:ver")

    def _bump(self, key: str) -> None:
        try:
            self._cache.incr(key)
        except ValueError:  # key missing or evicted
            self._cache.set(key, time.time_ns() // 1_000_000, VERSION_TTL)
