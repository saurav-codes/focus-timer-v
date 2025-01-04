from django.db import models
from django.contrib.auth import get_user_model
from apps.realtime_timer.models import Task


User = get_user_model()


# class DayPlan(models.Model):
#     """
#     Represents a plan for a specific day, which may include tasks, goals, 
#     and schedules. This model associates a user with their daily plan, 
#     allowing for organization and tracking of daily activities.
#     """
#     ...