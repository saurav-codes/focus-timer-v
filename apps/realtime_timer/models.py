from django.db import models
from uuid import uuid4
from django.utils import timezone
from django.core.validators import MinValueValidator, MaxValueValidator
from django.contrib.auth.models import AbstractUser
from timezone_field import TimeZoneField


class User(AbstractUser):
    timezone = TimeZoneField(default="UTC")


class FocusSession(models.Model):
    CAMEL_TECHNIQUE = "Camel"
    POMODORO_TECHNIQUE = "Pomodoro"
    FOCUS_52_17_TECHNIQUE = "52/17 Method"
    FOCUS_90_TECHNIQUE = "90-Minute Focus Sessions"
    FOCUS_2_HOURS_TECHNIQUE = "2-Hour Focus Blocks"
    FLOWTIME_TECHNIQUE = "Flowtime Technique"
    TECHNIQUE_CHOICES = [
        (CAMEL_TECHNIQUE, CAMEL_TECHNIQUE),
        (POMODORO_TECHNIQUE, POMODORO_TECHNIQUE),
        (FOCUS_52_17_TECHNIQUE, FOCUS_52_17_TECHNIQUE),
        (FOCUS_90_TECHNIQUE, FOCUS_90_TECHNIQUE),
        (FOCUS_2_HOURS_TECHNIQUE, FOCUS_2_HOURS_TECHNIQUE),
        (FLOWTIME_TECHNIQUE, FLOWTIME_TECHNIQUE),
    ]
    technique = models.CharField(max_length=30, choices=TECHNIQUE_CHOICES, default=CAMEL_TECHNIQUE)
    session_id = models.UUIDField(default=uuid4, primary_key=True, editable=False)
    owner = models.ForeignKey(User, on_delete=models.CASCADE, related_name="focus_sessions")
    duration_hours = models.PositiveIntegerField(
        help_text="Session duration in hours", validators=[MinValueValidator(0), MaxValueValidator(23)], default=0
    )
    duration_minutes = models.PositiveIntegerField(
        help_text="Session duration in minutes", validators=[MinValueValidator(0), MaxValueValidator(59)], default=0
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    current_cycle = models.ForeignKey(
        "FocusCycle", null=True, blank=True, on_delete=models.SET_NULL, related_name="current_session"
    )
    timer_start = models.DateTimeField(
        auto_now_add=True,
    )
    is_running = models.BooleanField(default=True)
    total_focus_time = models.DurationField(default=timezone.timedelta())
    is_completed = models.BooleanField(default=False)

    def __str__(self):
        return f"Session {self.session_id} by {self.owner.username}"


class FocusCycle(models.Model):
    FOCUS = "FOCUS"
    BREAK = "BREAK"
    CYCLE_TYPES = [
        (FOCUS, FOCUS),
        (BREAK, BREAK),
    ]
    session = models.ForeignKey(FocusSession, on_delete=models.CASCADE, related_name="focus_cycles")
    cycle_type = models.CharField(max_length=5, choices=CYCLE_TYPES)
    duration = models.PositiveIntegerField(
        help_text="Duration in minutes", validators=[MinValueValidator(0), MaxValueValidator(600)]
    )
    order = models.PositiveIntegerField()

    def __str__(self):
        return f"{self.cycle_type} - {self.duration} minutes"


class Task(models.Model):
    session = models.ForeignKey(FocusSession, on_delete=models.CASCADE, related_name="tasks")
    description = models.CharField(max_length=255)
    is_completed = models.BooleanField(default=False)

    def __str__(self):
        return self.description


class SessionFollower(models.Model):
    follower = models.ForeignKey(User, on_delete=models.CASCADE, related_name="followed_sessions")
    session = models.ForeignKey(FocusSession, on_delete=models.CASCADE, related_name="followers")
    joined_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ("follower", "session")

    def __str__(self):
        return f"{self.follower.username} following {self.session.session_id}"
