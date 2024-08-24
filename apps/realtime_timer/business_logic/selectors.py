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


def get_task_by_id(*, task_id: int) -> Task:
    return get_object_or_404(Task, id=task_id)


def is_user_a_session_follower(*, session: FocusSession, user) -> bool:
    """Is this user a follower of the given session?"""
    return session.followers.filter(follower=user).exists()  # type: ignore


def get_session_followers(*, session: FocusSession) -> QuerySet[SessionFollower]:
    return SessionFollower.objects.filter(session=session)
