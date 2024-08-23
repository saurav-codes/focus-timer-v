from django.db.models import QuerySet
from django.shortcuts import get_object_or_404
from django.utils import timezone
from ..models import FocusSession, SessionFollower, Task


def get_user_sessions(*, user) -> QuerySet[FocusSession]:
    return FocusSession.objects.filter(owner=user).order_by("-created_at")


def get_followed_sessions(*, user) -> QuerySet[FocusSession]:
    return FocusSession.objects.filter(followers__follower=user).order_by("-created_at")


def get_focus_session_by_id(*, session_id) -> FocusSession:
    return get_object_or_404(FocusSession, session_id=session_id)


def get_session_tasks(*, session: FocusSession) -> QuerySet[Task]:
    return Task.objects.filter(session=session)


def get_elapsed_time(*, session: FocusSession) -> timezone.timedelta:
    if session.is_running:
        return session.total_focus_time + (timezone.now() - session.timer_start)
    return session.total_focus_time


def get_task_by_id(*, task_id: int) -> Task:
    return get_object_or_404(Task, id=task_id)


def get_session_will_finish_at_with_timezone(*, session: FocusSession):
    # if user paused the session, then session end time will be calculated based on how much
    # time left in the session and how much total focus time is in the session
    ...


def get_session_followers(*, session: FocusSession):
    return SessionFollower.objects.filter(session=session)
