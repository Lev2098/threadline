from __future__ import annotations

from typing import Any

from rest_framework import status
from rest_framework.response import Response
from rest_framework.views import exception_handler as drf_exception_handler

from comments.domain.errors import DomainError, InvalidInput, NotFoundError


def exception_handler(exc: Exception, context: dict[str, Any]) -> Response | None:
    """Translate domain errors into one consistent JSON shape:

    ``{"code": "...", "message": "...", "errors": {"field": "message"}}``
    """
    if isinstance(exc, InvalidInput):
        return Response(
            {"code": exc.code, "message": "Please fix the highlighted fields.", "errors": exc.errors},
            status=status.HTTP_400_BAD_REQUEST,
        )
    if isinstance(exc, NotFoundError):
        return Response(
            {"code": exc.code, "message": exc.message, "errors": {exc.field: exc.message} if exc.field else {}},
            status=status.HTTP_404_NOT_FOUND,
        )
    if isinstance(exc, DomainError):
        return Response(
            {"code": exc.code, "message": exc.message, "errors": {exc.field or "non_field": exc.message}},
            status=status.HTTP_400_BAD_REQUEST,
        )

    response = drf_exception_handler(exc, context)
    if response is not None and isinstance(response.data, dict) and "detail" in response.data:
        detail = response.data["detail"]
        response.data = {"code": getattr(detail, "code", "error"), "message": str(detail), "errors": {}}
    return response
