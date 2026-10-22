"""Celery entry points (inbound adapter: the broker drives the application)."""

from __future__ import annotations

import logging

from celery import shared_task

from comments.adapters.outbound.events.celery_publisher import COMMENT_POSTED_TASK
from comments.bootstrap import container
from comments.domain.events import CommentPosted

log = logging.getLogger(__name__)


@shared_task(
    name=COMMENT_POSTED_TASK,
    autoretry_for=(Exception,),
    retry_backoff=2,
    retry_backoff_max=60,
    retry_jitter=True,
    max_retries=5,
)
def handle_comment_posted(payload: dict[str, int | None]) -> None:
    event = CommentPosted(
        comment_id=int(payload["comment_id"]),  # type: ignore[arg-type]
        root_id=int(payload["root_id"]),  # type: ignore[arg-type]
        parent_id=payload.get("parent_id"),
    )
    container().handle_comment_posted(event)
    log.info("comment %s handled", event.comment_id)
