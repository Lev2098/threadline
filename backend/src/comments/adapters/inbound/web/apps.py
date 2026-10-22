from django.apps import AppConfig


class WebConfig(AppConfig):
    """Server-rendered pages for crawlers and first paint: SEO, sitemap, robots."""

    name = "comments.adapters.inbound.web"
    label = "comments_web"
