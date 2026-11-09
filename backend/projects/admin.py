from django.contrib import admin
from django.contrib.auth.admin import GroupAdmin, UserAdmin
from django.contrib.auth.models import Group, User
from django.db import transaction

from .models import ProjectAccess, ProjectAuditEvent, ProjectStatusSetting, RiskFeedback


@admin.register(ProjectStatusSetting)
class ProjectStatusSettingAdmin(admin.ModelAdmin):
    list_display = ("status", "label", "enabled")


@admin.register(RiskFeedback)
class RiskFeedbackAdmin(admin.ModelAdmin):
    list_display = ("project", "user", "dismissed", "created_at")
    readonly_fields = ("project", "user", "signature", "dismissed", "reason", "snapshot", "created_at")

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False


class RoleAuditMixin:
    def save_model(self, request, obj, form, change):
        request.role_before = self.role_state(self.model.objects.select_for_update().get(pk=obj.pk)) if change else {}
        super().save_model(request, obj, form, change)

    def save_related(self, request, form, formsets, change):
        super().save_related(request, form, formsets, change)
        before = request.role_before
        after = self.role_state(form.instance)
        if before != after:
            self.log_change(request, form.instance, f"Role configuration: {before} → {after}")


class AuditedUserAdmin(RoleAuditMixin, UserAdmin):
    def role_state(self, user):
        return {
            "active": user.is_active, "staff": user.is_staff, "superuser": user.is_superuser,
            "groups": sorted(user.groups.values_list("name", flat=True)),
            "permissions": sorted(user.user_permissions.values_list("content_type__app_label", "codename")),
        }


class AuditedGroupAdmin(RoleAuditMixin, GroupAdmin):
    def role_state(self, group):
        return {
            "name": group.name,
            "permissions": sorted(group.permissions.values_list("content_type__app_label", "codename")),
        }


admin.site.unregister(User)
admin.site.unregister(Group)
admin.site.register(User, AuditedUserAdmin)
admin.site.register(Group, AuditedGroupAdmin)


@admin.register(ProjectAccess)
class ProjectAccessAdmin(admin.ModelAdmin):
    list_display = ("project", "user")
    list_select_related = ("project", "user")

    def record_access(self, request, access, action):
        ProjectAuditEvent.objects.create(
            project_id=access.project_id, actor=request.user, action=action,
            changes={"user_id": access.user_id},
        )

    def save_model(self, request, obj, form, change):
        previous = ProjectAccess.objects.select_for_update().get(pk=obj.pk) if change else None
        super().save_model(request, obj, form, change)
        if previous and (previous.project_id, previous.user_id) == (obj.project_id, obj.user_id):
            return
        if previous:
            self.record_access(request, previous, "access_revoked")
        self.record_access(request, obj, "access_granted")

    def delete_model(self, request, obj):
        self.record_access(request, obj, "access_revoked")
        super().delete_model(request, obj)

    def delete_queryset(self, request, queryset):
        with transaction.atomic():
            for access in queryset.select_for_update().iterator():
                self.record_access(request, access, "access_revoked")
            super().delete_queryset(request, queryset)
