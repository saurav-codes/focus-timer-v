from django.shortcuts import get_object_or_404
from django.utils import timezone
from django.db.models import Sum
from ..models import FocusSession, FocusCycle, FocusPeriod, FocusSessionFollower
from django.contrib.auth import get_user_model
from channels.db import database_sync_to_async
from uuid import UUID
import logging


logger = logging.getLogger(__name__)
User = get_user_model()


@database_sync_to_async
def get_last_focus_period_async(current_session: FocusSession):
    """
    this function is used to get the last focus period of the current session
    """
    return FocusPeriod.objects.filter(cycle=current_session.current_cycle).last()


@database_sync_to_async
def get_last_focus_period_locked_async(current_session: FocusSession):
    """
    this function is used to get the last focus period of the current session
    and lock the row to avoid race condition
    """
    return FocusPeriod.objects.select_for_update().filter(cycle=current_session.current_cycle).last()


# @database_sync_to_async
# def get_last_focus_period_for


@database_sync_to_async
def get_current_cycle_async(session: FocusSession):
    return FocusCycle.objects.get(id=session.current_cycle_id)  # type: ignore


@database_sync_to_async
def get_current_cycle_locked_async(session: FocusSession):
    return FocusCycle.objects.select_for_update().get(id=session.current_cycle_id)  # type: ignore


@database_sync_to_async
def get_session_by_id_async(session_id: UUID):
    return get_object_or_404(FocusSession, session_id=session_id)


@database_sync_to_async
def get_session_owner_async(session: FocusSession):
    return session.owner


@database_sync_to_async
def get_session_by_id_locked_async(session_id: UUID):
    """
    this function is used to get the session by id and lock the row to avoid race condition
    """
    return FocusSession.objects.select_for_update().get(session_id=session_id)


@database_sync_to_async
def get_completed_fp_duration_for_current_cycle_async(current_cycle: FocusCycle):
    completed_fp_duration = (
        FocusPeriod.objects.filter(
            cycle=current_cycle,
            ended_at__isnull=False,
        )
        .only("duration")
        .aggregate(total_time_focused=Sum("duration"))["total_time_focused"]
    )
    if not completed_fp_duration:
        # this means that this session is just started which is why it doesn't have
        # any finished sessions yet so we set an 0 timedelta so that it doesn't give
        # any error in calculations
        completed_fp_duration = timezone.timedelta(0)
    return completed_fp_duration


@database_sync_to_async
def get_duration_for_unfinished_fp_for_current_cycle_async(current_cycle: FocusCycle):
    timer_started_at_for_unfinished_fp = (
        FocusPeriod.objects.filter(
            cycle=current_cycle,
            ended_at__isnull=True,  # the current focus period
        )
        .only("started_at")
        .first()
    )
    if timer_started_at_for_unfinished_fp:
        duration_for_unfinished_fp = timezone.now() - timer_started_at_for_unfinished_fp.started_at
    else:
        duration_for_unfinished_fp = timezone.timedelta(0)
    return duration_for_unfinished_fp


async def get_all_focus_period_duration_for_current_cycle_async(current_cycle: FocusCycle) -> timezone.timedelta:
    total_time_focused_for_finished_fp = await get_completed_fp_duration_for_current_cycle_async(current_cycle)
    duration_for_unfinished_fp = await get_duration_for_unfinished_fp_for_current_cycle_async(current_cycle)
    return total_time_focused_for_finished_fp + duration_for_unfinished_fp


async def get_max_time_to_save_for_focus_period_async(current_cycle: FocusCycle):
    """
    this function returns the max duration we can save to current focus period
    while keeping in mind that sometime this method is called after a long time
    like when tab/browser sleeps & as they get active again, it's more time
    passed already then it was in cycle duration. so we need to make sure that
    we don't save more time then the cycle duration time left in the current cycle.
    """
    # first get all focus periods for the current cycle
    completed_fp_duration = await get_completed_fp_duration_for_current_cycle_async(current_cycle)
    return current_cycle.duration - completed_fp_duration


@database_sync_to_async
def calculate_total_focus_completed_async(session: FocusSession):
    # either choose the last resumed time or the started time
    # because the last resumed time will be None if the user started the session
    # and it will contain value if the user resumed the session
    # only call this method once the session is completed
    total_focused_time_qs = session.focus_periods.values("duration").aggregate(  # type:ignore
        total_time_focused=Sum("duration")
    )
    total_focused_time = total_focused_time_qs["total_time_focused"] or timezone.timedelta(0)
    return total_focused_time


async def get_timer_display_data(session: FocusSession):
    """
    return the remaining for current cycle.
    it uses cache and needs to be called every second to count
    correctly.
    call this inside the websocket consumer every second to send
    the update time to the client
    """
    data = {
        "remaining_time": 0,
        "current_cycle": {},
        "focus_cycles": {},
        "timer_state": session.timer_state,
    }
    if session.timer_state != FocusSession.TIMER_COMPLETED:
        # also get all focus period durations
        current_cycle = await get_current_cycle_async(session)
        all_focus_period_duration = await get_all_focus_period_duration_for_current_cycle_async(current_cycle)
        if current_cycle:
            remaining_time = current_cycle.duration.seconds - all_focus_period_duration.seconds
            logger.info(f"{session.session_id} Remaining time: {remaining_time}")
            if remaining_time < 0:
                # this could happen if scheduled_cycle_changes is not working properly
                # in that case, we will just show 0 remaining time
                remaining_time = 0
            data["remaining_time"] = remaining_time
            data["current_cycle"] = {
                "type": current_cycle.cycle_type,
                "order": current_cycle.order,
                "duration_seconds": current_cycle.duration.seconds,
            }
            # also add remaining cycles data
            focus_cycles = await database_sync_to_async(list)(
                session.focus_cycles.all()  # type: ignore
            )  # get all cycles after current one
            for focus_cycle in focus_cycles:
                data["focus_cycles"][str(focus_cycle.order)] = {
                    "type": focus_cycle.cycle_type,
                    "duration_seconds": focus_cycle.duration.seconds,
                    "is_completed": focus_cycle.is_completed,
                    "order": focus_cycle.order,
                }
    return data


@database_sync_to_async
def get_session_followers_list_async(session: FocusSession):
    session_followers = FocusSessionFollower.objects.filter(session=session)
    session_followers_list = {}
    for follower in session_followers:
        session_followers_list[follower.username] = {
            "user_type": follower.user_type,
            "joined_at": follower.joined_at.isoformat(),
        }
    return session_followers_list


@database_sync_to_async
def get_session_will_finish_at_async(*, session: FocusSession):
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
        duration_for_unfinished_fp = timezone.now() - timer_started_at_for_unfinished_fp.started_at
    else:
        duration_for_unfinished_fp = timezone.timedelta(0)
    total_time_focused = total_finished_fp + duration_for_unfinished_fp
    # time user has left to focus on this session
    total_time_left_to_focus = all_cycles_total_duration - total_time_focused
    # time user will finish the session at
    time_user_will_finish_at = timezone.now() + total_time_left_to_focus
    return time_user_will_finish_at.isoformat()
