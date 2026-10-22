from __future__ import annotations

from typing import Any

import pytest
from django.core.management import call_command

from comments.adapters.outbound.persistence.models import AttachmentRecord, CommentRecord

pytestmark = [pytest.mark.django_db(transaction=True), pytest.mark.integration]


def test_seed_demo_builds_consistent_threads(settings: Any, tmp_path: Any) -> None:
    settings.MEDIA_ROOT = str(tmp_path)
    call_command("seed_demo", reset=True, yes=True, bulk=300)

    roots = CommentRecord.objects.filter(parent__isnull=True)
    newest = roots.order_by("-created_at").first()
    assert newest is not None and newest.username == "Taras"  # curated threads are on top
    for root in roots.filter(client_id="demo"):
        replies = CommentRecord.objects.filter(root_id=root.id).exclude(pk=root.id)
        assert root.replies_count == replies.count()
        for reply in replies:
            assert reply.path.startswith(CommentRecord.objects.get(pk=reply.parent_id).path + ".")
    images = AttachmentRecord.objects.filter(kind="image")
    assert images.count() == 4 and all(a.width <= 320 and a.height <= 240 for a in images)
    assert AttachmentRecord.objects.filter(kind="text").count() == 1
    assert CommentRecord.objects.count() == 300 + 43
