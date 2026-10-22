from __future__ import annotations

from typing import Any

from django.db import DatabaseError, InterfaceError, OperationalError
from django.http import HttpRequest, JsonResponse
from rest_framework import status
from rest_framework.response import Response
from rest_framework.views import exception_handler as drf_exception_handler

from comments.domain.errors import DomainError, InvalidInput, NotFoundError, ServiceUnavailable


def exception_handler(exc: Exception, context: dict[str, Any]) -> Response | None:
    """Translate every API error into one JSON shape:

    ``{"code": "...", "message": "...", "errors": {"field": "message"}}``
    """
    if isinstance(exc, InvalidInput):
        return _response(exc.code, "Please fix the highlighted fields.", exc.errors, status.HTTP_400_BAD_REQUEST)
    if isinstance(exc, NotFoundError):
        errors = {exc.field: exc.message} if exc.field else {}
        return _response(exc.code, exc.message, errors, status.HTTP_404_NOT_FOUND)
    if isinstance(exc, ServiceUnavailable):
        return _response(exc.code, exc.message, {}, status.HTTP_503_SERVICE_UNAVAILABLE)
    if isinstance(exc, (OperationalError, InterfaceError)) or type(exc) is DatabaseError:
        # Database unreachable (restart, failover): a retryable 503, not a 500.
        return _response(
            "unavailable",
            "The service is temporarily unavailable. Please try again.",
            {},
            status.HTTP_503_SERVICE_UNAVAILABLE,
        )
    if isinstance(exc, DomainError):
        return _response(exc.code, exc.message, {exc.field or "non_field": exc.message}, status.HTTP_400_BAD_REQUEST)

    response = drf_exception_handler(exc, context)
    if response is None:
        return None
    data = response.data
    if isinstance(data, dict) and "detail" in data:
        detail = data["detail"]
        response.data = {"code": getattr(detail, "code", "error"), "message": str(detail), "errors": {}}
    elif isinstance(data, dict):
        # Serializer validation errors: {"field": ["msg", ...]} -> {"field": "msg"}
        errors = {field: _first(messages) for field, messages in data.items()}
        response.data = {"code": "invalid", "message": "Please fix the highlighted fields.", "errors": errors}
    elif isinstance(data, list):
        response.data = {"code": "invalid", "message": _first(data), "errors": {}}
    return response


def _first(messages: Any) -> str:
    if isinstance(messages, list) and messages:
        return _first(messages[0])
    if isinstance(messages, dict) and messages:
        return _first(next(iter(messages.values())))
    return str(messages)


def _response(code: str, message: str, errors: dict[str, str], http_status: int) -> Response:
    return Response({"code": code, "message": message, "errors": errors}, status=http_status)


def json_not_found(request: HttpRequest, exception: Exception | None = None) -> JsonResponse:
    return JsonResponse({"code": "not_found", "message": "Not found.", "errors": {}}, status=404)


def json_server_error(request: HttpRequest) -> JsonResponse:
    return JsonResponse({"code": "server_error", "message": "Internal server error.", "errors": {}}, status=500)
