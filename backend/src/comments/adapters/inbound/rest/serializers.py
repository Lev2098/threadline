"""Request parsing and OpenAPI documentation only.

Business validation happens in the domain; these serializers just coerce the
transport format (multipart / JSON) into primitives. Limits mirrored here are
for early rejection and docs, the domain remains the source of truth.
"""

from __future__ import annotations

from rest_framework import serializers


class PostCommentSerializer(serializers.Serializer):
    username = serializers.CharField(max_length=64, allow_blank=True, trim_whitespace=True)
    email = serializers.CharField(max_length=254, allow_blank=True)
    home_page = serializers.CharField(max_length=2048, required=False, allow_blank=True, default="")
    # Generous cap only against abuse; the domain enforces 5000 after normalizing CRLF.
    text = serializers.CharField(max_length=10_000, allow_blank=True, trim_whitespace=False)
    captcha_key = serializers.CharField(max_length=64)
    captcha = serializers.CharField(max_length=16, allow_blank=True)
    parent_id = serializers.IntegerField(required=False, allow_null=True, min_value=1)
    attachment = serializers.FileField(required=False, allow_null=True, allow_empty_file=False)


class PreviewSerializer(serializers.Serializer):
    text = serializers.CharField(max_length=10_000, allow_blank=True, trim_whitespace=False)


class ListQuerySerializer(serializers.Serializer):
    ordering = serializers.ChoiceField(
        choices=["created_at", "-created_at", "username", "-username", "email", "-email"],
        required=False,
        default="-created_at",
    )
    page = serializers.IntegerField(required=False, default=1, min_value=1, max_value=1_000_000)


class ThreadQuerySerializer(serializers.Serializer):
    # Shape and depth are validated by the use case (comments.domain.comment.is_valid_path).
    cursor = serializers.CharField(max_length=1200, required=False, allow_blank=True)
    limit = serializers.IntegerField(required=False, default=500, min_value=1, max_value=500)


class SearchQuerySerializer(serializers.Serializer):
    q = serializers.CharField(max_length=200)
    page = serializers.IntegerField(required=False, default=1, min_value=1, max_value=400)


class AttachmentOut(serializers.Serializer):
    kind = serializers.ChoiceField(choices=["image", "text"])
    url = serializers.CharField()
    name = serializers.CharField()
    size = serializers.IntegerField()
    width = serializers.IntegerField(allow_null=True)
    height = serializers.IntegerField(allow_null=True)


class CommentOut(serializers.Serializer):
    id = serializers.IntegerField()
    parent_id = serializers.IntegerField(allow_null=True)
    root_id = serializers.IntegerField()
    depth = serializers.IntegerField()
    path = serializers.CharField()
    username = serializers.CharField()
    email = serializers.CharField()
    home_page = serializers.CharField(allow_null=True)
    html = serializers.CharField(help_text="Sanitized XHTML, safe to render.")
    created_at = serializers.DateTimeField()
    replies_count = serializers.IntegerField()
    attachment = AttachmentOut(allow_null=True)


class CommentPageOut(serializers.Serializer):
    items = CommentOut(many=True)
    page = serializers.IntegerField()
    pages = serializers.IntegerField()
    page_size = serializers.IntegerField()
    total = serializers.IntegerField()


class ThreadOut(serializers.Serializer):
    items = CommentOut(many=True)
    next_cursor = serializers.CharField(allow_null=True)


class SessionOut(serializers.Serializer):
    token = serializers.CharField()
    client_id = serializers.CharField()
    expires_in = serializers.IntegerField()


class CaptchaOut(serializers.Serializer):
    key = serializers.CharField()
    image = serializers.CharField(help_text="data:image/png;base64,...")
    ttl = serializers.IntegerField()


class PreviewOut(serializers.Serializer):
    html = serializers.CharField()
