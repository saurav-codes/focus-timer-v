from django.db.models import QuerySet
from django.shortcuts import get_object_or_404
from django.utils.formats import date_format
from django.utils import timezone
from django.db.models import Sum
from ..models import FocusSession, SessionFollower, Task
from django.contrib.auth import get_user_model

User = get_user_model()


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


def get_session_will_finish_at(*, request_user, session: FocusSession):
    user = User.objects.get(username=request_user.username)
    user_timezone = timezone.now().astimezone(user.timezone)  # type: ignore
    # total time user will spend on this session
    all_cycles_total_duration = session.focus_cycles.all().only("duration").aggregate(  # type: ignore
        total_duration=Sum("duration")
    )["total_duration"] or timezone.timedelta(0)
    # now find out how much user has already spent on this session
    total_finished_fp = session.focus_periods.filter(ended_at__isnull=False).only("duration").aggregate(  # type: ignore
        total_time_focused=Sum("duration")
    )["total_time_focused"] or timezone.timedelta(0)
    timer_started_at_for_unfinished_fp = (
        session.focus_periods.filter(  # type: ignore
            ended_at__isnull=True,  # the current focus period
        )
        .only("started_at")
        .first()
    )
    # time user has spent on the current focus period
    if timer_started_at_for_unfinished_fp:
        duration_for_unfinished_fp = user_timezone - timer_started_at_for_unfinished_fp.started_at
    else:
        duration_for_unfinished_fp = timezone.timedelta(0)
    total_time_focused = total_finished_fp + duration_for_unfinished_fp
    # time user has left to focus on this session
    total_time_left_to_focus = all_cycles_total_duration - total_time_focused
    # time user will finish the session at
    time_user_will_finish_at = user_timezone + total_time_left_to_focus
    # format the time in readable format
    formatted_time = date_format(time_user_will_finish_at, format="F j, Y, g:i A")
    return f"{formatted_time} {user.timezone}"  # type: ignore
