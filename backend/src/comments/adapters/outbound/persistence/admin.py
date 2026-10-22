from django.contrib import admin

from comments.adapters.outbound.persistence.models import AttachmentRecord, CommentRecord


class AttachmentInline(admin.StackedInline):
    model = AttachmentRecord
    extra = 0
    can_delete = True


@admin.register(CommentRecord)
class CommentAdmin(admin.ModelAdmin):
    list_display = ("id", "username", "email", "created_at", "replies_count", "ip")
    list_filter = ("created_at",)
    search_fields = ("username", "email", "client_id", "ip")
    readonly_fields = ("parent", "root", "path", "client_id", "ip", "user_agent", "replies_count", "created_at")
    raw_id_fields = ("parent", "root")
    inlines = [AttachmentInline]
    show_full_result_count = False  # COUNT(*) over a million rows on every page load is wasteful
