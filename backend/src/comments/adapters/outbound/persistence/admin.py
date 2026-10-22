from django.contrib import admin

from comments.adapters.outbound.persistence.models import AttachmentRecord, CommentRecord


class AttachmentInline(admin.StackedInline):
    model = AttachmentRecord
    extra = 0
    can_delete = False

    def has_change_permission(self, request, obj=None):  # type: ignore[no-untyped-def]
        return False


@admin.register(CommentRecord)
class CommentAdmin(admin.ModelAdmin):
    list_display = ("id", "username", "email", "created_at", "replies_count", "ip")
    list_filter = ("created_at",)
    search_fields = ("username", "email", "client_id", "ip")
    # Read-only browsing: editing or deleting rows here would bypass domain
    # validation, sanitizing, counters, cache invalidation and the search index.
    readonly_fields = (
        "parent",
        "root",
        "path",
        "username",
        "email",
        "home_page",
        "text_source",
        "text_html",
        "client_id",
        "ip",
        "user_agent",
        "replies_count",
        "created_at",
    )
    raw_id_fields = ("parent", "root")
    inlines = [AttachmentInline]
    show_full_result_count = False  # COUNT(*) over a million rows on every page load is wasteful

    def has_add_permission(self, request):  # type: ignore[no-untyped-def]
        return False

    def has_delete_permission(self, request, obj=None):  # type: ignore[no-untyped-def]
        return False
