from django.db import models
from django.contrib.auth.models import User


class Technique(models.Model):
    name = models.CharField(max_length=100)
    description = models.TextField()
    creator = models.ForeignKey(User, on_delete=models.CASCADE, related_name="created_techniques")
    is_custom = models.BooleanField(default=False)
    shuffle_enabled = models.BooleanField(default=False)
    increment_enabled = models.BooleanField(default=False)
    decrement_enabled = models.BooleanField(default=False)


class IntervalPattern(models.Model):
    technique = models.ForeignKey(Technique, on_delete=models.CASCADE, related_name="interval_patterns")
    focus_duration = models.PositiveIntegerField()  # in seconds
    break_duration = models.PositiveIntegerField()  # in seconds
    order = models.PositiveIntegerField()
    is_focus = models.BooleanField(default=True)


class Session(models.Model):
    creator = models.ForeignKey(User, on_delete=models.CASCADE, related_name="created_sessions")
    technique = models.ForeignKey(Technique, on_delete=models.CASCADE)
    start_time = models.DateTimeField(auto_now_add=True)
    end_time = models.DateTimeField(null=True, blank=True)
    total_duration = models.PositiveIntegerField()  # in seconds
    current_interval = models.PositiveIntegerField(default=0)
    status = models.CharField(
        max_length=20,
        choices=[("active", "Active"), ("paused", "Paused"), ("completed", "Completed")],
        default="active",
    )
    is_community = models.BooleanField(default=False)


class Interval(models.Model):
    session = models.ForeignKey(Session, on_delete=models.CASCADE, related_name="intervals")
    start_time = models.DateTimeField()
    end_time = models.DateTimeField(null=True, blank=True)
    is_focus = models.BooleanField()
    duration = models.PositiveIntegerField()  # in seconds


class SessionFeedback(models.Model):
    session = models.ForeignKey(Session, on_delete=models.CASCADE, related_name="feedback")
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    rating = models.PositiveIntegerField()  # You might want to add choices or validation
    timestamp = models.DateTimeField(auto_now_add=True)


class UserSession(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    session = models.ForeignKey(Session, on_delete=models.CASCADE)
    join_time = models.DateTimeField(auto_now_add=True)
    leave_time = models.DateTimeField(null=True, blank=True)
