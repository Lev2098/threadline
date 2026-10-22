"""Comment -> JSON shape shared by REST responses and WebSocket pushes, so a
comment rendered from a live event is identical to one loaded over HTTP."""

from __future__ import annotations

from typing import Any

from django.core.files.storage import default_storage

from comments.domain.comment import Comment


def comment_to_dict(comment: Comment) -> dict[str, Any]:
    attachment = None
    if comment.attachment:
        attachment = {
            "kind": comment.attachment.kind.value,
            "url": default_storage.url(comment.attachment.path),
            "name": comment.attachment.original_name,
            "size": comment.attachment.size,
            "width": comment.attachment.width,
            "height": comment.attachment.height,
        }
    return {
        "id": comment.id,
        "parent_id": comment.parent_id,
        "root_id": comment.root_id,
        "depth": comment.depth,
        "path": comment.path,
        "username": comment.author.username.value,
        "email": comment.author.email.value,
        "home_page": comment.author.home_page.value if comment.author.home_page else None,
        "html": comment.text.html,
        "created_at": comment.created_at.isoformat() if comment.created_at else None,
        "replies_count": comment.replies_count,
        "attachment": attachment,
    }
