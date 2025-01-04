from django.urls import path
from .views import DayPlannerView, CalendarView, UpdateScheduleView

app_name = 'timetable'

urlpatterns = [
    path('', DayPlannerView.as_view(), name='day-planner'),
    path('calendar/', CalendarView.as_view(), name='calendar'),
    path('update-schedule/', UpdateScheduleView.as_view(), name='update-schedule'),
]
