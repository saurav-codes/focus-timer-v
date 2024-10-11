from django.db import models
from uuid import uuid4
from django.urls import reverse
from django.utils import timezone
from django.contrib.auth.models import AbstractUser
from timezone_field import TimeZoneField
import logging

logger = logging.getLogger(__name__)


class User(AbstractUser):
    timezone = TimeZoneField(default="UTC")


class FocusSession(models.Model):
    CAMEL_TECHNIQUE = "Camel"
    POMODORO_TECHNIQUE = "Pomodoro"
    FOCUS_52_17_TECHNIQUE = "52/17 Method"
    FOCUS_90_TECHNIQUE = "90-Minute Focus Sessions"
    FOCUS_2_HOURS_TECHNIQUE = "2-Hour Focus Blocks"
    FLOWTIME_TECHNIQUE = "Flowtime Technique"
    CUSTOM_TECHNIQUE = "Custom Technique"
    TIMER_RUNNING = "running"
    TIMER_PAUSED = "paused"
    TIMER_COMPLETED = "completed"
    TECHNIQUE_CHOICES = [
        (CAMEL_TECHNIQUE, CAMEL_TECHNIQUE),
        (POMODORO_TECHNIQUE, POMODORO_TECHNIQUE),
        (FOCUS_52_17_TECHNIQUE, FOCUS_52_17_TECHNIQUE),
        (FOCUS_90_TECHNIQUE, FOCUS_90_TECHNIQUE),
        (FOCUS_2_HOURS_TECHNIQUE, FOCUS_2_HOURS_TECHNIQUE),
        (FLOWTIME_TECHNIQUE, FLOWTIME_TECHNIQUE),
        (CUSTOM_TECHNIQUE, CUSTOM_TECHNIQUE),
    ]
    TIMER_STATE_CHOICES = [
        (TIMER_RUNNING, TIMER_RUNNING),
        (TIMER_PAUSED, TIMER_PAUSED),
        (TIMER_COMPLETED, TIMER_COMPLETED),
    ]
    technique = models.CharField(max_length=30, choices=TECHNIQUE_CHOICES, default=CAMEL_TECHNIQUE)
    session_id = models.UUIDField(default=uuid4, primary_key=True, editable=False)
    owner = models.ForeignKey(User, on_delete=models.CASCADE, related_name="focus_sessions")
    created_at = models.DateTimeField(auto_now_add=True)
    current_cycle = models.ForeignKey(
        "FocusCycle", on_delete=models.CASCADE, default=None, null=True, blank=True, related_name="current_cycle"
    )
    # saving a instance means that the timer has started
    timer_started_at = models.DateTimeField(auto_now_add=True)
    # total time spent focusing
    total_focus_completed = models.DurationField(default=timezone.timedelta)
    timer_state = models.CharField(choices=TIMER_STATE_CHOICES, default=TIMER_RUNNING, max_length=9)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return f"Session {self.session_id} by {self.owner.username}"

    async def asave(self, *args, **kwargs):
        trigger_timer_sync = kwargs.pop("trigger_timer_sync", False)
        await super().asave(*args, **kwargs)
        # trigger the sync_timer consumer method
        # to sync the timer for the clients who are actively
        # working on this session
        if trigger_timer_sync:
            from apps.realtime_timer.business_logic.services import trigger_sync_timer_for_all_connected_clients

            logger.info(f"model:focus_session:save:sync_timer triggered for session {self.session_id}")
            await trigger_sync_timer_for_all_connected_clients(str(self.session_id))

    def get_absolute_url(self):
        return reverse("realtime_timer:session-detail-view", kwargs={"session_id": self.session_id})

    @property
    def label(self):
        return f"Session {self.session_id}"


class FocusPeriod(models.Model):
    """
    One Focus Period b/w each start and pause/stop of FocusSession
    there can be multiple focus periods for a single session and a single
    focus cycle. for filtering, we can simply filter by session
    and cycle__cycle_type=FOCUS to get all focus periods for a session
    and cycle__cycle_type=BREAK to get all break periods for a session
    """

    session = models.ForeignKey(FocusSession, on_delete=models.CASCADE, related_name="focus_periods")
    cycle = models.ForeignKey("FocusCycle", on_delete=models.CASCADE, related_name="focus_cycles")
    started_at = models.DateTimeField(auto_now_add=True)
    ended_at = models.DateTimeField(null=True, blank=True)
    duration = models.DurationField(default=timezone.timedelta)

    def __str__(self):
        return f"Focus Period {self.pk} for {self.session.session_id}"


class FocusCycle(models.Model):
    """
    This will work as template to execute the focus session
    in a specific order and duration
    """

    FOCUS = "FOCUS"
    BREAK = "BREAK"
    CYCLE_TYPES = [
        (FOCUS, FOCUS),
        (BREAK, BREAK),
    ]
    session = models.ForeignKey(FocusSession, on_delete=models.CASCADE, related_name="focus_cycles")
    cycle_type = models.CharField(max_length=5, choices=CYCLE_TYPES)
    duration = models.DurationField(help_text="Duration in minutes")
    order = models.PositiveIntegerField()
    is_completed = models.BooleanField(default=False)
    is_scheduled = models.BooleanField(default=False)

    def __str__(self):
        return f"{self.cycle_type} - {self.duration} minutes"

    class Meta:
        ordering = ["order"]


class Task(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name="tasks")
    session = models.ForeignKey(FocusSession, on_delete=models.CASCADE, related_name="tasks")
    description = models.CharField(max_length=255)
    is_completed = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return self.description


class FocusSessionFollower(models.Model):
    session = models.ForeignKey(FocusSession, related_name="followers", on_delete=models.CASCADE)
    user = models.ForeignKey(User, on_delete=models.CASCADE, null=True, blank=True)
    username = models.CharField(max_length=150)  # Store username separately for anonymous users
    joined_at = models.DateTimeField(auto_now_add=True)
    user_type = models.CharField(max_length=20, choices=[("guest", "Guest"), ("authenticated", "Authenticated")])

    class Meta:
        unique_together = ("session", "username")
