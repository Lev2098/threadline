from __future__ import annotations

from typing import Any

from django.core.cache import BaseCache
from redis.exceptions import RedisError

from comments.domain.errors import ServiceUnavailable

PREFIX = "captcha:"


class RedisCaptchaStore:
    """GETDEL makes read-and-consume atomic: two parallel requests can't
    both pass with the same captcha."""

    def __init__(self, client: Any) -> None:
        self._client = client

    def save(self, key: str, answer: str, ttl_seconds: int) -> None:
        try:
            self._client.set(PREFIX + key, answer, ex=ttl_seconds)
        except RedisError as exc:
            raise _unavailable() from exc

    def pop(self, key: str) -> str | None:
        try:
            value = self._client.getdel(PREFIX + key)
        except RedisError as exc:
            raise _unavailable() from exc
        return value.decode() if isinstance(value, bytes) else value


def _unavailable() -> ServiceUnavailable:
    # Without the captcha store nothing can be posted; say so instead of a bare 500.
    return ServiceUnavailable("Posting is temporarily unavailable. Please try again in a minute.")


class CacheCaptchaStore:
    """Fallback for single-process setups (dev, tests) without Redis."""

    def __init__(self, cache: BaseCache) -> None:
        self._cache = cache

    def save(self, key: str, answer: str, ttl_seconds: int) -> None:
        self._cache.set(PREFIX + key, answer, ttl_seconds)

    def pop(self, key: str) -> str | None:
        value: str | None = self._cache.get(PREFIX + key)
        self._cache.delete(PREFIX + key)
        return value


class FixedAnswerCaptchaStore:
    """Load-testing only: every captcha accepts one known answer, so scripted
    users can post. Enabled solely by LOADTEST_MODE=true (see settings)."""

    def __init__(self, inner: RedisCaptchaStore | CacheCaptchaStore, answer: str) -> None:
        self._inner = inner
        self._answer = answer

    def save(self, key: str, answer: str, ttl_seconds: int) -> None:
        self._inner.save(key, self._answer, ttl_seconds)

    def pop(self, key: str) -> str | None:
        return self._inner.pop(key)
