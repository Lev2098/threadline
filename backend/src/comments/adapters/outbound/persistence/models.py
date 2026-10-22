"""ORM records. They live in the adapter layer and never leave it:
the repository maps them to domain ``Comment`` objects.
"""

from __future__ import annotations

from django.db import models
from django.db.models.functions import Lower
from django.utils import timezone

ROOTS = models.Q(parent__isnull=True)


class CommentRecord(models.Model):
    id = models.BigAutoField(primary_key=True)
    parent = models.ForeignKey(
        "self", null=True, blank=True, on_delete=models.CASCADE, related_name="children", db_index=False
    )
    # Indexed via the composite (root, path) index below.
    root = models.ForeignKey("self", null=True, blank=True, on_delete=models.CASCADE, related_name="+", db_index=False)
    # Materialized path of zero-padded ids, see comments.domain.comment.child_path.
    path = models.TextField(default="")

    # Author data is denormalized into the row: the root table is sorted by
    # these columns, and a JOIN on the hottest query would defeat the indexes.
    username = models.CharField(max_length=64)
    email = models.CharField(max_length=254)
    home_page = models.CharField(max_length=2048, blank=True, default="")

    text_source = models.TextField()
    text_html = models.TextField()

    client_id = models.CharField(max_length=64, db_index=True)
    ip = models.GenericIPAddressField(null=True, blank=True)
    user_agent = models.CharField(max_length=512, blank=True, default="")

    replies_count = models.PositiveIntegerField(default=0)
    created_at = models.DateTimeField(default=timezone.now)

    class Meta:
        db_table = "comments"
        indexes = [
            # One partial index per sortable column of the root table. Each
            # includes id as a tiebreaker, so pagination is deterministic and
            # ORDER BY ... LIMIT is an index scan with no sort step.
            models.Index(fields=["-created_at", "-id"], condition=ROOTS, name="comments_root_created_idx"),
            # INCLUDE the raw column: PostgreSQL only plans an index-only scan for
            # an expression index when the referenced column is in the index too.
            # Without it a deep OFFSET by username took 1.7 s (heap fetch per row).
            models.Index(
                Lower("username"), "id", condition=ROOTS, include=["username"], name="comments_root_username_idx"
            ),
            models.Index(Lower("email"), "id", condition=ROOTS, include=["email"], name="comments_root_email_idx"),
            # Whole thread in depth-first order: WHERE root_id = ? ORDER BY path.
            models.Index(fields=["root", "path"], name="comments_thread_path_idx"),
            models.Index(fields=["parent"], name="comments_parent_idx"),
        ]

    def __str__(self) -> str:
        return f"#{self.pk} by {self.username}"


class AttachmentRecord(models.Model):
    class Kind(models.TextChoices):
        IMAGE = "image"
        TEXT = "text"

    comment = models.OneToOneField(CommentRecord, on_delete=models.CASCADE, related_name="attachment")
    kind = models.CharField(max_length=8, choices=Kind.choices)
    file = models.CharField(max_length=255)
    original_name = models.CharField(max_length=255)
    size = models.PositiveIntegerField()
    width = models.PositiveSmallIntegerField(null=True, blank=True)
    height = models.PositiveSmallIntegerField(null=True, blank=True)

    class Meta:
        db_table = "comment_attachments"

    def __str__(self) -> str:
        return self.original_name
