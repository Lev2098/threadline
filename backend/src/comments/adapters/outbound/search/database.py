from __future__ import annotations

from django.db.models import Q

from comments.adapters.outbound.persistence.models import CommentRecord
from comments.domain.comment import Comment


class DatabaseSearchIndex:
    """Fallback used when ELASTICSEARCH_URL is not configured.

    Fine for development; on a million rows ILIKE is a sequential scan, which
    is exactly why production uses the Elasticsearch adapter.
    """

    def index(self, comment: Comment) -> None:
        return None  # the table *is* the index

    def search(self, query: str, offset: int, limit: int) -> tuple[list[int], int]:
        qs = CommentRecord.objects.filter(Q(text_source__icontains=query) | Q(username__icontains=query))
        total = qs.count()
        ids = list(qs.order_by("-created_at", "-id").values_list("id", flat=True)[offset : offset + limit])
        return ids, total
