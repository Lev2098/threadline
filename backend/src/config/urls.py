from django.conf import settings
from django.contrib import admin
from django.urls import include, path
from django.views.decorators.csrf import csrf_exempt
from drf_spectacular.views import SpectacularAPIView, SpectacularSwaggerView
from strawberry.django.views import GraphQLView

from comments.adapters.inbound.graphql.schema import schema
from comments.adapters.inbound.rest.views import readyz

handler404 = "comments.adapters.inbound.rest.errors.json_not_found"
handler500 = "comments.adapters.inbound.rest.errors.json_server_error"

urlpatterns = [
    path("api/v1/", include("comments.adapters.inbound.rest.urls")),
    path("api/schema", SpectacularAPIView.as_view(), name="schema"),
    path("api/docs", SpectacularSwaggerView.as_view(url_name="schema"), name="docs"),
    # Read-only queries + preview; no cookie auth, so CSRF does not apply.
    path(
        "graphql",
        csrf_exempt(GraphQLView.as_view(schema=schema, graphql_ide="graphiql" if settings.DEBUG else None)),
    ),
    path("admin/", admin.site.urls),
    path("readyz", readyz),
    path("", include("comments.adapters.inbound.web.urls")),
]

if settings.DEBUG or settings.SERVE_MEDIA:
    # Normally the edge (nginx) serves media straight from the shared volume.
    # SERVE_MEDIA is for platforms without shared volumes (Railway): nginx falls
    # back here and adds the hardening headers itself (frontend/docker).
    from django.urls import re_path
    from django.views.static import serve

    urlpatterns.insert(0, re_path(r"^media/(?P<path>.*)$", serve, {"document_root": settings.MEDIA_ROOT}))
