# -*- coding: utf-8 -*-
from django.contrib import admin

from .models import User, FocusSession, FocusPeriod, FocusCycle, Task, FocusSessionFollower


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
        "current_cycle",
        "timer_started_at",
        "total_focus_completed",
        "timer_state",
    )
    list_filter = (
        "owner",
        "created_at",
        "current_cycle",
        "timer_started_at",
    )
    date_hierarchy = "created_at"


@admin.register(FocusPeriod)
class FocusPeriodAdmin(admin.ModelAdmin):
    list_display = (
        "id",
        "session",
        "cycle",
        "started_at",
        "ended_at",
        "duration",
    )
    list_filter = ("started_at", "ended_at")


@admin.register(FocusCycle)
class FocusCycleAdmin(admin.ModelAdmin):
    list_display = ("id", "session", "cycle_type", "duration", "order")
    raw_id_fields = ("session",)


@admin.register(Task)
class TaskAdmin(admin.ModelAdmin):
    list_display = (
        "id",
        "user",
        "session",
        "description",
        "is_completed",
        "created_at",
        "updated_at",
    )
    list_filter = (
        "user",
        "session",
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
    list_filter = ("user_type", "joined_at")
    date_hierarchy = "joined_at"
