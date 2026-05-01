from django.contrib import admin
from django.utils.html import format_html
from .models import DisciplineCase, SuspensionRecord, DisciplineAuditLog


# =========================================
# 🔷 INLINE: SUSPENSION
# =========================================
class SuspensionInline(admin.StackedInline):
    model = SuspensionRecord
    extra = 0
    can_delete = True


# =========================================
# 🔷 BULK ACTIONS
# =========================================
@admin.action(description="Archive selected cases")
def archive_cases(modeladmin, request, queryset):
    queryset.update(is_archived=True)


@admin.action(description="Restore selected cases")
def restore_cases(modeladmin, request, queryset):
    queryset.update(is_archived=False)


@admin.action(description="Mark as resolved")
def resolve_cases(modeladmin, request, queryset):
    queryset.update(status='resolved')


# =========================================
# 🔷 DISCIPLINE CASE ADMIN
# =========================================
@admin.register(DisciplineCase)
class DisciplineCaseAdmin(admin.ModelAdmin):

    list_display = (
        'student',
        'title',
        'case_type_badge',
        'action_type_badge',
        'status_badge',
        'severity_points',
        'suspension_status',
        'is_archived',
        'date_reported',
    )

    list_filter = (
        'case_type',
        'action_type',
        'status',
        'is_archived',
        'date_reported',
    )

    search_fields = (
        'student__first_name',
        'student__last_name',
        'student__registration_number',
        'title',
        'description',
        'action_taken',
    )

    readonly_fields = ('date_reported', 'date_updated')

    ordering = ('-date_reported',)

    inlines = [SuspensionInline]

    actions = [archive_cases, restore_cases, resolve_cases]

    list_per_page = 20

    # =========================================
    # 🔥 BADGES (MODERN UI)
    # =========================================

    def status_badge(self, obj):
        color = "#f39c12" if obj.status == "open" else "#27ae60"
        return format_html(
            '<span style="color:white;background:{};padding:4px 8px;border-radius:6px;">{}</span>',
            color,
            obj.get_status_display()
        )
    status_badge.short_description = "Status"


    def case_type_badge(self, obj):
        color = "#e74c3c" if obj.case_type == "major" else "#3498db"
        return format_html(
            '<span style="color:white;background:{};padding:4px 8px;border-radius:6px;">{}</span>',
            color,
            obj.get_case_type_display()
        )
    case_type_badge.short_description = "Type"


    def action_type_badge(self, obj):
        colors = {
            "warning": "#f1c40f",
            "punishment": "#e67e22",
            "suspension": "#c0392b",
        }
        color = colors.get(obj.action_type, "#7f8c8d")
        return format_html(
            '<span style="color:white;background:{};padding:4px 8px;border-radius:6px;">{}</span>',
            color,
            obj.get_action_type_display()
        )
    action_type_badge.short_description = "Action"


    # =========================================
    # 🔥 SUSPENSION STATUS
    # =========================================
    def suspension_status(self, obj):
        if hasattr(obj, 'suspension'):

            s = obj.suspension

            if s.is_overdue():
                return format_html('<span style="color:red;">Overdue</span>')

            if s.status == "active":
                return format_html('<span style="color:orange;">Active</span>')

            if s.status == "completed":
                return format_html('<span style="color:green;">Completed</span>')

        return "-"
    suspension_status.short_description = "Suspension"


# =========================================
# 🔷 SUSPENSION ADMIN
# =========================================
@admin.register(SuspensionRecord)
class SuspensionAdmin(admin.ModelAdmin):

    list_display = (
        'case',
        'start_date',
        'end_date',
        'status_badge',
        'overdue_display',
    )

    list_filter = ('status', 'start_date', 'end_date')

    search_fields = (
        'case__student__first_name',
        'case__student__last_name',
        'case__title',
    )

    def status_badge(self, obj):
        color = "#f39c12" if obj.status == "active" else "#27ae60"
        return format_html(
            '<span style="color:white;background:{};padding:4px 8px;border-radius:6px;">{}</span>',
            color,
            obj.status.capitalize()
        )
    status_badge.short_description = "Status"


    def overdue_display(self, obj):
        if obj.is_overdue():
            return format_html('<span style="color:red;">Yes</span>')
        return "No"
    overdue_display.short_description = "Overdue"


# =========================================
# 🔷 AUDIT LOG ADMIN
# =========================================
@admin.register(DisciplineAuditLog)
class DisciplineAuditLogAdmin(admin.ModelAdmin):

    list_display = (
        'case',
        'action',
        'performed_by',
        'timestamp',
    )

    list_filter = ('action', 'timestamp')

    search_fields = (
        'case__title',
        'performed_by__username',
    )

    readonly_fields = ('timestamp',)

    ordering = ('-timestamp',)