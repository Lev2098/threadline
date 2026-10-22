from __future__ import annotations

from collections.abc import Callable, Iterator, Sequence
from contextlib import AbstractContextManager

from django.db import transaction
from django.db.models import F, OrderBy, QuerySet
from django.db.models.functions import Lower

from comments.adapters.outbound.persistence.models import ROOTS, AttachmentRecord, CommentRecord
from comments.domain.attachment import Attachment, AttachmentKind
from comments.domain.comment import Comment, child_path
from comments.domain.markup import CommentText
from comments.domain.values import (
    Author,
    ClientFingerprint,
    Email,
    HomePage,
    Ordering,
    SortDirection,
    SortField,
    UserName,
)


class DjangoTransactions:
    def atomic(self) -> AbstractContextManager[None]:
        return transaction.atomic()

    def on_commit(self, callback: Callable[[], None]) -> None:
        transaction.on_commit(callback)


class DjangoCommentRepository:
    def __init__(self, using: str | None = None) -> None:
        # ``using="default"`` pins reads to the primary when a replica router is active.
        self._using = using

    def _records(self) -> QuerySet[CommentRecord]:
        qs = CommentRecord.objects.select_related("attachment")
        return qs.using(self._using) if self._using else qs

    def add(self, comment: Comment) -> Comment:
        parent = None
        if comment.parent_id is not None:
            parent = CommentRecord.objects.only("id", "root_id", "path").get(pk=comment.parent_id)

        with transaction.atomic():
            record = CommentRecord.objects.create(
                parent_id=comment.parent_id,
                username=comment.author.username.value,
                email=comment.author.email.value,
                home_page=comment.author.home_page.value if comment.author.home_page else "",
                text_source=comment.text.source,
                text_html=comment.text.html,
                client_id=comment.fingerprint.client_id,
                ip=comment.fingerprint.ip,
                user_agent=comment.fingerprint.user_agent[:512],
            )
            # The path embeds the row's own id, which exists only after INSERT.
            record.root_id = parent.root_id if parent else record.id
            record.path = child_path(parent.path if parent else "", record.id)
            CommentRecord.objects.filter(pk=record.pk).update(root_id=record.root_id, path=record.path)
            if parent:
                # F() keeps the counter correct under concurrent replies.
                CommentRecord.objects.filter(pk=record.root_id).update(replies_count=F("replies_count") + 1)

            if comment.attachment:
                record.attachment = AttachmentRecord.objects.create(
                    comment=record,
                    kind=comment.attachment.kind.value,
                    file=comment.attachment.path,
                    original_name=comment.attachment.original_name,
                    size=comment.attachment.size,
                    width=comment.attachment.width,
                    height=comment.attachment.height,
                )
        return _to_domain(record)

    def get(self, comment_id: int) -> Comment | None:
        record = self._records().filter(pk=comment_id).first()
        return _to_domain(record) if record else None

    def get_many(self, ids: Sequence[int]) -> list[Comment]:
        by_id = {r.id: r for r in self._records().filter(pk__in=ids)}
        return [_to_domain(by_id[i]) for i in ids if i in by_id]

    def list_roots(self, ordering: Ordering, offset: int, limit: int) -> list[Comment]:
        # Deferred join: page through the narrow index first (ids only), then
        # load the 25 full rows. Deep OFFSETs skip index entries, not table rows.
        ids = list(
            CommentRecord.objects.filter(ROOTS)
            .order_by(*_order_by(ordering))
            .values_list("id", flat=True)[offset : offset + limit]
        )
        return self.get_many(ids)

    def count_roots(self) -> int:
        return CommentRecord.objects.filter(ROOTS).count()

    def thread(self, root_id: int, after_path: str | None, limit: int) -> list[Comment]:
        qs = self._records().filter(root_id=root_id).exclude(pk=root_id)
        if after_path:
            qs = qs.filter(path__gt=after_path)
        return [_to_domain(r) for r in qs.order_by("path")[:limit]]

    def iterate_all(self, chunk_size: int = 2000) -> Iterator[Comment]:
        """Used by the search reindex command."""
        for record in self._records().order_by("id").iterator(chunk_size=chunk_size):
            yield _to_domain(record)


def _order_by(ordering: Ordering) -> list[OrderBy]:
    column = {
        SortField.CREATED_AT: F("created_at"),
        SortField.USERNAME: Lower("username"),
        SortField.EMAIL: Lower("email"),
    }[ordering.field]
    if ordering.direction is SortDirection.DESC:
        return [column.desc(), F("id").desc()]
    return [column.asc(), F("id").asc()]


def _to_domain(record: CommentRecord) -> Comment:
    attachment = None
    try:
        att = record.attachment
    except AttachmentRecord.DoesNotExist:
        att = None
    if att is not None:
        attachment = Attachment(
            kind=AttachmentKind(att.kind),
            path=att.file,
            original_name=att.original_name,
            size=att.size,
            width=att.width,
            height=att.height,
        )
    return Comment(
        id=record.id,
        parent_id=record.parent_id,
        root_id=record.root_id,
        path=record.path,
        author=Author(
            UserName(record.username),
            Email(record.email),
            HomePage(record.home_page) if record.home_page else None,
        ),
        # Stored HTML was produced by CommentText.parse; it is not re-parsed on read.
        text=CommentText(source=record.text_source, html=record.text_html),
        fingerprint=ClientFingerprint(client_id=record.client_id, ip=record.ip, user_agent=record.user_agent),
        attachment=attachment,
        created_at=record.created_at,
        replies_count=record.replies_count,
    )
