# -*- coding: utf-8 -*-
from django.contrib import admin

from .models import User, FocusSession, FocusPeriod, FocusCycle, Task, FocusSessionFollower
from .business_logic.selectors import get_total_time_to_focus


@admin.register(User)
class UserAdmin(admin.ModelAdmin):
    list_display = (
        "id",
        "password",
        "last_login",
        "is_superuser",
        "username",
        "first_name",
        "last_name",
        "email",
        "is_staff",
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
        "created_at",
        "total_focus_completed",
        "total_time_to_focus",
        "timer_state",
    )
    list_filter = (
        "owner",
        "created_at",
        "current_cycle",
    )
    date_hierarchy = "created_at"
    readonly_fields = ("total_time_to_focus",)

    def total_time_to_focus(self, obj):
        return get_total_time_to_focus(obj)


@admin.register(FocusPeriod)
class FocusPeriodAdmin(admin.ModelAdmin):
    list_display = (
        "id",
        "session",
        "cycle",
        "started_at",
        "ended_at",
        "duration",
        "user",
    )
    list_filter = ("started_at", "ended_at", "user")
    raw_id_fields = ("session", "cycle")


@admin.register(FocusCycle)
class FocusCycleAdmin(admin.ModelAdmin):
    list_display = (
        "id",
        "session",
        "cycle_type",
        "duration",
        "order",
        "is_completed",
        "is_scheduled",
    )
    list_filter = ("is_completed", "is_scheduled")


@admin.register(Task)
class TaskAdmin(admin.ModelAdmin):
    list_display = (
        "id",
        "user",
        "description",
        "is_completed",
        "created_at",
        "updated_at",
    )
    list_filter = (
        "user",
        "is_completed",
        "created_at",
        "updated_at",
    )
    date_hierarchy = "created_at"


@admin.register(FocusSessionFollower)
class FocusSessionFollowerAdmin(admin.ModelAdmin):
    list_display = (
        "id",
        "session",
        "user",
        "username",
        "joined_at",
        "user_type",
    )
    list_filter = ("joined_at",)
    date_hierarchy = "joined_at"
