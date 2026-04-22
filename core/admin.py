from django.contrib import admin
from django.utils import timezone

from .models import Player, Club, ShortlistEntry, TrialRequest, TrialFeedback, Report

admin.site.register(Player)
admin.site.register(Club)
admin.site.register(ShortlistEntry)
admin.site.register(TrialRequest)
admin.site.register(TrialFeedback)


@admin.register(Report)
class ReportAdmin(admin.ModelAdmin):
    list_display = ("report_type", "reason", "reporter", "status", "created_at", "resolver", "resolved_at")
    list_filter = ("report_type", "reason", "status")
    search_fields = ("reporter__username", "details", "admin_notes")
    readonly_fields = ("created_at", "resolved_at", "resolver")

    def save_model(self, request, obj, form, change):
        if obj.status in ["resolved", "dismissed"]:
            if not obj.resolver:
                obj.resolver = request.user
            if not obj.resolved_at:
                obj.resolved_at = timezone.now()
        elif obj.status == "open":
            obj.resolver = None
            obj.resolved_at = None

        super().save_model(request, obj, form, change)