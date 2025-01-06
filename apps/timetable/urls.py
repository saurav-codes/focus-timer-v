from django.urls import path
from .views import DayPlannerView, CalendarView, UpdateScheduleView, TasksAddView

app_name = 'timetable'

urlpatterns = [
    path('planner/', DayPlannerView.as_view(), name='day-planner'),
    path('calendar/', CalendarView.as_view(), name='calendar-view'),
    path('update-schedule/', UpdateScheduleView.as_view(), name='update-schedule'),
    path('tasks-add/', TasksAddView.as_view(), name='tasks-add-view'),
]
