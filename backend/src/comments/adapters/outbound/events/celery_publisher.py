from __future__ import annotations

import logging
from collections.abc import Callable
from dataclasses import asdict

from comments.application.ports import TransactionManager
from comments.domain.events import CommentPosted

log = logging.getLogger(__name__)

BROADCAST_TASK = "comments.broadcast_comment"
INDEX_TASK = "comments.index_comment"

Payload = dict[str, object]


class CeleryEventPublisher:
    """Hands domain events to the broker (RabbitMQ) after commit.

    Publishing before commit would let a worker pick the task up and not find
    the row yet; ``on_commit`` also drops the event if the transaction rolls back.

    If the broker is unreachable the comment is already committed, so the user
    must still get a success response: the event is then handled inline as a
    best effort (``fallback``) instead of surfacing a 500 for saved data.
    """

    def __init__(
        self,
        transactions: TransactionManager,
        send: Callable[[Payload], None],
        fallback: Callable[[CommentPosted], None],
    ) -> None:
        self._tx = transactions
        self._send = send
        self._fallback = fallback

    def publish(self, event: CommentPosted) -> None:
        self._tx.on_commit(lambda: self._deliver(event))

    def _deliver(self, event: CommentPosted) -> None:
        try:
            self._send(asdict(event))
        except Exception:
            log.exception("Broker unavailable; handling comment %s inline", event.comment_id)
            try:
                self._fallback(event)
            except Exception:
                log.exception("Inline handling of comment %s failed; run search_reindex to recover", event.comment_id)
