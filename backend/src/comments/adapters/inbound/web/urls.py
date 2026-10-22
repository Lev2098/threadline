from django.urls import path

from comments.adapters.inbound.web import views

urlpatterns = [
    path("", views.home, name="home"),
    path("t/<int:comment_id>", views.thread, name="thread"),
    path("robots.txt", views.robots_txt, name="robots"),
    path("sitemap.xml", views.sitemap_index, name="sitemap-index"),
    path("sitemaps/pages.xml", views.sitemap_pages, name="sitemap-pages"),
    path("sitemaps/threads-<int:number>.xml", views.sitemap_threads, name="sitemap-threads"),
]
