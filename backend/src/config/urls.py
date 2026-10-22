from django.conf import settings
from django.contrib import admin
from django.urls import include, path
from django.views.decorators.csrf import csrf_exempt
from drf_spectacular.views import SpectacularAPIView, SpectacularSwaggerView
from strawberry.django.views import GraphQLView

from comments.adapters.inbound.graphql.schema import schema
from comments.adapters.inbound.rest.views import healthz, readyz

urlpatterns = [
    path("api/v1/", include("comments.adapters.inbound.rest.urls")),
    path("api/schema", SpectacularAPIView.as_view(), name="schema"),
    path("api/docs", SpectacularSwaggerView.as_view(url_name="schema"), name="docs"),
    # Read-only queries + preview; no cookie auth, so CSRF does not apply.
    path("graphql", csrf_exempt(GraphQLView.as_view(schema=schema, graphql_ide="graphiql"))),
    path("admin/", admin.site.urls),
    path("healthz", healthz),
    path("readyz", readyz),
]

if settings.DEBUG:
    from django.conf.urls.static import static

    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
