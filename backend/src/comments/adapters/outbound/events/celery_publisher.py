from __future__ import annotations

from collections.abc import Callable
from dataclasses import asdict

from comments.application.ports import TransactionManager
from comments.domain.events import CommentPosted

COMMENT_POSTED_TASK = "comments.handle_comment_posted"


class CeleryEventPublisher:
    """Hands domain events to the broker (RabbitMQ) after commit.

    Publishing before commit would let a worker pick the task up and not find
    the row yet; ``on_commit`` also drops the event if the transaction rolls back.
    The task is passed in rather than imported, keeping this outbound adapter
    independent of the inbound task module.
    """

    def __init__(self, transactions: TransactionManager, send: Callable[[dict[str, object]], None]) -> None:
        self._tx = transactions
        self._send = send

    def publish(self, event: CommentPosted) -> None:
        payload = asdict(event)
        self._tx.on_commit(lambda: self._send(payload))
