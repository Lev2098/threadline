"""Celery entry points (inbound adapter: the broker drives the application)."""

from __future__ import annotations

import logging

from celery import shared_task

from comments.adapters.outbound.events.celery_publisher import BROADCAST_TASK, INDEX_TASK
from comments.bootstrap import container
from comments.domain.events import CommentPosted

log = logging.getLogger(__name__)


def _event(payload: dict[str, int | None]) -> CommentPosted:
    return CommentPosted(
        comment_id=int(payload["comment_id"]),  # type: ignore[arg-type]
        root_id=int(payload["root_id"]),  # type: ignore[arg-type]
        parent_id=payload.get("parent_id"),
    )


# Live push is only useful while it is fresh: a few quick retries, then give up.
@shared_task(name=BROADCAST_TASK, autoretry_for=(Exception,), retry_backoff=1, max_retries=3)
def broadcast_comment(payload: dict[str, int | None]) -> None:
    container().handle_comment_posted.broadcast(_event(payload))


# Indexing must eventually happen: retries with backoff up to 10 min cover an
# Elasticsearch restart; indexing by id is idempotent, so redelivery is safe.
@shared_task(
    name=INDEX_TASK,
    autoretry_for=(Exception,),
    retry_backoff=5,
    retry_backoff_max=600,
    retry_jitter=True,
    max_retries=12,
)
def index_comment(payload: dict[str, int | None]) -> None:
    container().handle_comment_posted.index(_event(payload))
    log.info("comment %s indexed", payload["comment_id"])
