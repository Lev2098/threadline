from __future__ import annotations

from asgiref.sync import async_to_sync
from channels.layers import get_channel_layer

from comments.adapters.serialization import comment_to_dict
from comments.domain.comment import Comment

GROUP = "comments.live"


class ChannelsBroadcaster:
    """Fan-out through the Redis channel layer: every ASGI replica receives
    the event and forwards it to its own WebSocket clients."""

    def comment_posted(self, comment: Comment) -> None:
        layer = get_channel_layer()
        if layer is None:
            return
        async_to_sync(layer.group_send)(GROUP, {"type": "comment.posted", "comment": comment_to_dict(comment)})
