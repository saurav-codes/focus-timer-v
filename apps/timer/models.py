# timer/models.py

from django.db import models
from django.contrib.auth.models import User


class FocusSession(models.Model):
    TECHNIQUE_CHOICES = [
        ("CAMEL", "Camel"),
        ("POMODORO", "Pomodoro"),
        ("FLOW_2H", "2 Hour Flow"),
        ("FLOW_4H", "4 Hour Flow"),
        ("CUSTOM", "Custom"),
    ]

    user = models.ForeignKey(User, on_delete=models.CASCADE)
    start_time = models.DateTimeField(auto_now_add=True)
    end_time = models.DateTimeField(null=True, blank=True)
    technique = models.CharField(max_length=10, choices=TECHNIQUE_CHOICES)
    total_duration = models.DurationField()
    is_streamer_session = models.BooleanField(default=False)

    def __str__(self):
        return f"{self.user.username}'s {self.technique} session on {self.start_time.date()}"


class FocusInterval(models.Model):
    session = models.ForeignKey(FocusSession, on_delete=models.CASCADE, related_name="intervals")
    start_time = models.DateTimeField()
    end_time = models.DateTimeField(null=True, blank=True)
    is_break = models.BooleanField(default=False)

    def __str__(self):
        interval_type = "Break" if self.is_break else "Focus"
        return f"{interval_type} interval for {self.session}"


class UserProfile(models.Model):
    user = models.OneToOneField(User, on_delete=models.CASCADE)
    is_streamer = models.BooleanField(default=False)
    theme_preference = models.CharField(max_length=5, choices=[("light", "light"), ("dark", "dark")], default="light")

    def __str__(self):
        return f"{self.user.username}'s profile"


class CustomTechnique(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    name = models.CharField(max_length=50)
    focus_duration = models.DurationField()
    break_duration = models.DurationField()

    def __str__(self):
        return f"{self.user.username}'s {self.name} technique"
