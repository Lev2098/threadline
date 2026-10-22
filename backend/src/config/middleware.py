from __future__ import annotations

from collections.abc import Callable

from django.http import HttpRequest, HttpResponse, JsonResponse

HEALTH_PATHS = frozenset({"/healthz"})


class HealthCheckMiddleware:
    """Answers liveness probes before Host validation.

    Container healthchecks call 127.0.0.1, which a production
    DJANGO_ALLOWED_HOSTS (only the public domain) would reject with 400 and
    mark a healthy container as down. Must be first in MIDDLEWARE.
    """

    def __init__(self, get_response: Callable[[HttpRequest], HttpResponse]) -> None:
        self.get_response = get_response

    def __call__(self, request: HttpRequest) -> HttpResponse:
        if request.path in HEALTH_PATHS:
            return JsonResponse({"status": "ok"})
        return self.get_response(request)
