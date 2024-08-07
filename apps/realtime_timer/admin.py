from django.contrib import admin

from .models import FocusSession, FocusCycle, Task, SessionFollower, User


@admin.register(User)
class UserAdmin(admin.ModelAdmin):
    list_display = (
        "id",
        "last_login",
        "is_superuser",
        "username",
        "first_name",
        "last_name",
        "email",
        "is_active",
        "date_joined",
        "timezone",
    )
    list_filter = (
        "last_login",
        "is_superuser",
        "is_staff",
        "is_active",
        "date_joined",
    )
    raw_id_fields = ("groups", "user_permissions")


@admin.register(FocusSession)
class FocusSessionAdmin(admin.ModelAdmin):
    list_display = (
        "technique",
        "session_id",
        "owner",
        "duration_hours",
        "duration_minutes",
        "created_at",
        "updated_at",
        "current_cycle",
        "timer_start",
        "is_running",
        "total_focus_time",
        "is_completed",
    )
    list_filter = (
        "owner",
        "created_at",
        "updated_at",
        "current_cycle",
        "timer_start",
        "is_running",
        "is_completed",
    )
    date_hierarchy = "created_at"


@admin.register(FocusCycle)
class FocusCycleAdmin(admin.ModelAdmin):
    list_display = ("id", "session", "cycle_type", "duration", "order")
    list_filter = ("session",)


@admin.register(Task)
class TaskAdmin(admin.ModelAdmin):
    list_display = ("id", "session", "description", "is_completed")
    list_filter = ("session", "is_completed")


@admin.register(SessionFollower)
class SessionFollowerAdmin(admin.ModelAdmin):
    list_display = ("id", "follower", "session", "joined_at")
    list_filter = ("follower", "session", "joined_at")
    date_hierarchy = "joined_at"
