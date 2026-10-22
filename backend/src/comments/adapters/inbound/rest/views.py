from __future__ import annotations

import base64
import ipaddress
from typing import Any

from django.conf import settings
from django.db import connection
from django.http import HttpRequest, JsonResponse
from drf_spectacular.utils import OpenApiParameter, extend_schema
from rest_framework import status
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.views import APIView

from comments.adapters.inbound.rest import serializers as s
from comments.adapters.inbound.rest.auth import ClientPrincipal, HasClientToken, issue_token
from comments.adapters.serialization import comment_to_dict
from comments.application.dto import ListRootsQuery, PostCommentCommand
from comments.bootstrap import container
from comments.domain.attachment import Upload
from comments.domain.values import ClientFingerprint, Ordering


def client_ip(request: HttpRequest) -> str | None:
    raw = request.META.get("HTTP_X_REAL_IP") if settings.TRUST_PROXY_HEADERS else None
    raw = raw or request.META.get("REMOTE_ADDR")
    try:
        return str(ipaddress.ip_address((raw or "").strip()))
    except ValueError:
        return None


def page_payload(page: Any) -> dict[str, Any]:
    return {
        "items": [comment_to_dict(c) for c in page.items],
        "page": page.page,
        "pages": page.pages,
        "page_size": page.page_size,
        "total": page.total,
    }


class SessionView(APIView):
    throttle_scope = "session"
    authentication_classes: list[type] = []

    @extend_schema(request=None, responses=s.SessionOut, summary="Issue an anonymous client token")
    def post(self, request: Request) -> Response:
        token, client_id, ttl = issue_token()
        return Response({"token": token, "client_id": client_id, "expires_in": ttl}, status=status.HTTP_201_CREATED)


class CaptchaView(APIView):
    throttle_scope = "captcha"

    @extend_schema(responses=s.CaptchaOut, summary="New single-use captcha image")
    def get(self, request: Request) -> Response:
        captcha = container().issue_captcha()
        image = "data:image/png;base64," + base64.b64encode(captcha.image_png).decode()
        response = Response({"key": captcha.key, "image": image, "ttl": captcha.ttl_seconds})
        response["Cache-Control"] = "no-store"
        return response


class CommentListView(APIView):
    throttle_scope = "read"

    def get_permissions(self) -> list[Any]:
        return [HasClientToken()] if self.request.method == "POST" else super().get_permissions()

    def get_throttles(self) -> list[Any]:
        self.throttle_scope = "post" if self.request.method == "POST" else "read"
        return super().get_throttles()

    @extend_schema(
        parameters=[s.ListQuerySerializer],
        responses=s.CommentPageOut,
        summary="Root comments, 25 per page (default: newest first)",
    )
    def get(self, request: Request) -> Response:
        params = s.ListQuerySerializer(data=request.query_params)
        params.is_valid(raise_exception=True)
        page = container().list_root_comments(
            ListRootsQuery(
                ordering=Ordering.parse(params.validated_data["ordering"]), page=params.validated_data["page"]
            )
        )
        return Response(page_payload(page))

    @extend_schema(request=s.PostCommentSerializer, responses={201: s.CommentOut}, summary="Post a comment or reply")
    def post(self, request: Request) -> Response:
        body = s.PostCommentSerializer(data=request.data)
        body.is_valid(raise_exception=True)
        data = body.validated_data
        principal: ClientPrincipal = request.user

        upload = None
        if file := data.get("attachment"):
            upload = Upload(filename=file.name or "", content=file.read())

        comment = container().post_comment(
            PostCommentCommand(
                username=data["username"],
                email=data["email"],
                home_page=data.get("home_page"),
                text=data["text"],
                captcha_key=data["captcha_key"],
                captcha_answer=data["captcha"],
                parent_id=data.get("parent_id"),
                upload=upload,
                fingerprint=ClientFingerprint(
                    client_id=principal.client_id,
                    ip=client_ip(request._request),
                    user_agent=request.META.get("HTTP_USER_AGENT", ""),
                ),
            )
        )
        return Response(comment_to_dict(comment), status=status.HTTP_201_CREATED)


class PreviewView(APIView):
    throttle_scope = "preview"

    @extend_schema(
        request=s.PreviewSerializer, responses=s.PreviewOut, summary="Render text exactly as it will be saved"
    )
    def post(self, request: Request) -> Response:
        body = s.PreviewSerializer(data=request.data)
        body.is_valid(raise_exception=True)
        return Response({"html": container().preview_comment(body.validated_data["text"])})


class CommentDetailView(APIView):
    throttle_scope = "read"

    @extend_schema(responses=s.CommentOut, summary="One comment by id (used for permalinks)")
    def get(self, request: Request, comment_id: int) -> Response:
        return Response(comment_to_dict(container().get_comment(comment_id)))


class ThreadView(APIView):
    throttle_scope = "read"

    @extend_schema(
        parameters=[s.ThreadQuerySerializer],
        responses=s.ThreadOut,
        summary="All replies of a root comment, depth-first; paginate with next_cursor",
    )
    def get(self, request: Request, root_id: int) -> Response:
        params = s.ThreadQuerySerializer(data=request.query_params)
        params.is_valid(raise_exception=True)
        thread = container().get_thread(
            root_id, params.validated_data.get("cursor") or None, params.validated_data["limit"]
        )
        return Response({"items": [comment_to_dict(c) for c in thread.items], "next_cursor": thread.next_cursor})


class SearchView(APIView):
    throttle_scope = "read"

    @extend_schema(
        parameters=[OpenApiParameter("q", str, required=True), OpenApiParameter("page", int)],
        responses=s.CommentPageOut,
        summary="Full-text search (Elasticsearch)",
    )
    def get(self, request: Request) -> Response:
        params = s.SearchQuerySerializer(data=request.query_params)
        params.is_valid(raise_exception=True)
        page = container().search_comments(params.validated_data["q"], params.validated_data["page"])
        return Response(page_payload(page))


def readyz(request: HttpRequest) -> JsonResponse:
    try:
        with connection.cursor() as cursor:
            cursor.execute("SELECT 1")
    except Exception:
        return JsonResponse({"status": "db unavailable"}, status=503)
    return JsonResponse({"status": "ready"})
