from django.urls import path

from comments.adapters.inbound.rest import views

urlpatterns = [
    path("session", views.SessionView.as_view(), name="session"),
    path("captcha", views.CaptchaView.as_view(), name="captcha"),
    path("comments", views.CommentListView.as_view(), name="comments"),
    path("comments/preview", views.PreviewView.as_view(), name="comments-preview"),
    path("comments/search", views.SearchView.as_view(), name="comments-search"),
    path("comments/<int:comment_id>", views.CommentDetailView.as_view(), name="comments-detail"),
    path("comments/<int:root_id>/thread", views.ThreadView.as_view(), name="comments-thread"),
]
