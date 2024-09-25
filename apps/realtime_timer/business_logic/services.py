import asyncio
import random
import logging
from django.forms import ValidationError
from django.http import HttpRequest, HttpResponse

from ..models import FocusPeriod, FocusSession, FocusCycle, FocusSessionFollower
from django.contrib.auth import get_user_model
from django.db.models import Sum
from django.utils import timezone
from channels.db import database_sync_to_async
from django.conf import settings
import redis_lock
from channels.layers import get_channel_layer
from asgiref.sync import async_to_sync

User = get_user_model()

logger = logging.getLogger(__name__)


def create_focus_cycles_and_session(
    focus_session_form_cleaned_data: dict,
    fetched_focus_cycle_data_from_post_request: dict,
    owner,
) -> FocusSession | ValidationError:
    """
    Create a focus session and its focus cycles\n
    example of fetched_focus_cycle_data_from_post_request:
    ```{
        1: {
            "type": "FOCUS",
            "duration": 25
        },
        2: {
            "type": "BREAK",
            "duration": 5
        },
        ....
    }
    note: saving a new object will start the timer immediately
    """
    focus_session = FocusSession.objects.create(
        owner=owner,
        technique=focus_session_form_cleaned_data["technique"],
    )
    logger.info(f"{owner.username} Created focus session with ID: {focus_session.session_id}")

    # Create focus cycles
    for order, cycle_data in fetched_focus_cycle_data_from_post_request.items():
        try:
            fc = FocusCycle(
                session=focus_session,
                cycle_type=cycle_data["type"],
                duration=timezone.timedelta(minutes=cycle_data["duration"]),
                order=order,
            )
            fc.full_clean()
            fc.save()
            logger.info(f"{owner.username} Created focus cycle with order: {order} and type: {cycle_data['type']}")
        except ValidationError as e:
            focus_session.delete()
            logger.error(f"{owner.username} Validation error while creating focus cycle: {e}")
            return e

    # since we have created the focus cycles but the instance is not updated
    # we need to refresh the instance from the database
    focus_session.refresh_from_db()

    # Set the current cycle to the first cycle
    # TODO: use django stub to fix these type errors
    first_cycle = focus_session.focus_cycles.first()  # type: ignore
    if first_cycle:
        focus_session.current_cycle = first_cycle
        focus_session.save()
        logger.info(f"{owner.username} Set first cycle as current cycle for session ID: {focus_session.session_id}")

    # create first focus period because the focus session is started.
    FocusPeriod.objects.create(session=focus_session, cycle=first_cycle)
    logger.info(f"{owner.username} Created first focus period for session ID: {focus_session.session_id}")
    return focus_session


def fetch_focus_cycles_data_from_post_request(request: HttpRequest) -> dict | HttpResponse:
    cycles_types = request.POST.getlist("focus_cycle_type")
    cycles_durations = request.POST.getlist("focus_cycle_duration")
    try:
        return {
            i: {"type": t, "duration": int(d)} for i, (t, d) in enumerate(zip(cycles_types, cycles_durations), start=1)
        }
    except ValueError:
        logger.error("Duration must be an integer", extra={"request": request})
        return HttpResponse(
            "Duration must be an integer like 1, 2, ... upto any number of minutes you want to focus or break"
        )


class AsyncTimerService:
    def __init__(self, session: FocusSession, user) -> None:
        self.session = session
        self.user = user
        logger.info(f"AsyncTimerService initialized for session ID: {session.session_id}, user: {user.username}")

    @database_sync_to_async
    def _get_timer_state(self):
        return self.session.timer_state

    @database_sync_to_async
    def _get_session_owner(self):
        return self.session.owner

    @database_sync_to_async
    def _get_current_cycle(self):
        return FocusCycle.objects.get(id=self.session.current_cycle_id)  # type: ignore

    async def _create_new_focus_period(self):
        current_cycle = await self._get_current_cycle()
        await database_sync_to_async(FocusPeriod.objects.create)(session=self.session, cycle=current_cycle)
        logger.info(
            f"{self.user.username} Created new focus period for session ID: {self.session.session_id}, cycle ID: {current_cycle.id}"
        )

    @database_sync_to_async
    def _get_completed_fp_duration_for_current_cycle(self, current_cycle):
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
    def _get_duration_for_unfinished_fp_for_current_cycle(self, current_cycle):
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

    async def _get_all_focus_period_duration_for_current_cycle(self, current_cycle) -> timezone.timedelta:
        total_time_focused_for_finished_fp = await self._get_completed_fp_duration_for_current_cycle(current_cycle)
        duration_for_unfinished_fp = await self._get_duration_for_unfinished_fp_for_current_cycle(current_cycle)
        return total_time_focused_for_finished_fp + duration_for_unfinished_fp

    async def _save_last_focus_period_of_current_session(self):
        """
        this function is used to end the last focus period of the current session
        it's used when the timer is paused or stopped or when the user is done with the current cycle
        so we save the time for the last focus period.
        """
        # get the last focus period
        last_focus_period = await database_sync_to_async(self.session.focus_periods.last)()  # type:ignore
        if last_focus_period and not last_focus_period.ended_at:
            # if the last focus period is not ended, end it
            last_focus_period.ended_at = timezone.now()
            # calculate the duration of the last focus period
            fp_duration = last_focus_period.ended_at - last_focus_period.started_at
            # sometime this method is called after a long time like
            # when tab/browser sleeps & as they get active again, it's
            # more time passed already then it was in cycle.
            max_time_to_save_for_focus_period = await self._get_max_time_to_save_for_focus_period()
            last_focus_period.duration = min(fp_duration, max_time_to_save_for_focus_period)
            await last_focus_period.asave()
            logger.info(
                f"{self.user.username} Ended last focus period with duration: {last_focus_period.duration}, ID: {last_focus_period.id}"
            )
            logger.info(
                f"{self.user.username} choosing a minimum b/w {fp_duration} and {max_time_to_save_for_focus_period}"
            )
            logger.info(
                f"{self.user.username} last focus period ended with duration: {last_focus_period.duration} and id: {last_focus_period.id}"
            )
            if fp_duration > max_time_to_save_for_focus_period:
                logger.warning(
                    f"{self.user.username} ⚠️ Lag detected: {fp_duration - max_time_to_save_for_focus_period}"
                )

    async def _get_max_time_to_save_for_focus_period(self):
        """
        this function returns the max duration we can save to current focus period
        while keeping in mind that sometime this method is called after a long time
        like when tab/browser sleeps & as they get active again, it's more time
        passed already then it was in cycle duration. so we need to make sure that
        we don't save more time then the cycle duration time left in the current cycle.
        """
        # first get all focus periods for the current cycle
        current_cycle = await self._get_current_cycle()
        completed_fp_duration = await self._get_completed_fp_duration_for_current_cycle(current_cycle)
        return current_cycle.duration - completed_fp_duration

    async def _calculate_total_focus_completed(self):
        # either choose the last resumed time or the started time
        # because the last resumed time will be None if the user started the session
        # and it will contain value if the user resumed the session
        # only call this method once the session is completed
        total_focused_time_qs = await database_sync_to_async(
            self.session.focus_periods.values("duration").aggregate  # type:ignore
        )(  # type: ignore
            total_time_focused=Sum("duration")
        )
        total_focused_time = total_focused_time_qs["total_time_focused"] or timezone.timedelta(0)
        return total_focused_time

    async def pause_timer(self):
        if self.session.timer_state == FocusSession.TIMER_RUNNING:
            logger.info(f"{self.user.username} Pausing timer for session ID: {self.session.session_id}")
            self.session.timer_state = FocusSession.TIMER_PAUSED
            await self.session.asave()
            await self._save_last_focus_period_of_current_session()

    async def stop_timer(self):
        """
        doesn't matter if the session is completed or not.
        we will just calculate all the time spent and end the last focus period
        and mark the session as completed
        """
        logger.info(f"{self.user.username} Stopping timer for session ID: {self.session.session_id}")
        await self.pause_timer()  # make sure the last focus period is ended
        self.session.total_focus_completed = await self._calculate_total_focus_completed()
        self.session.timer_state = FocusSession.TIMER_COMPLETED
        await self.session.asave()

    async def resume_timer(self):
        if self.session.timer_state == FocusSession.TIMER_PAUSED:
            # just add a new focus period
            await self._create_new_focus_period()
            self.session.timer_state = FocusSession.TIMER_RUNNING
            await self.session.asave()
            logger.info(f"{self.user.username} Resumed timer for session ID: {self.session.session_id}")

    async def toggle_timer(self):
        logger.info(f"{self.user.username} Toggling timer for session ID: {self.session.session_id}")
        timer_state = await self._get_timer_state()
        if timer_state == FocusSession.TIMER_RUNNING:
            await self.pause_timer()
            return "paused"
        elif timer_state == FocusSession.TIMER_PAUSED:
            await self.resume_timer()
            return "resumed"

    async def get_timer_display_data(self):
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
            "timer_state": self.session.timer_state,
        }
        if not self.session.timer_state == FocusSession.TIMER_COMPLETED:
            current_cycle = await self._get_current_cycle()
            # also get all focus period durations
            all_focus_period_duration = await self._get_all_focus_period_duration_for_current_cycle(current_cycle)
            if current_cycle:
                remaining_time = current_cycle.duration.seconds - all_focus_period_duration.seconds
                logger.info(f"{self.user.username} Remaining time: {remaining_time}")
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
                    self.session.focus_cycles.all()  # type: ignore
                )  # get all cycles after current one
                for focus_cycle in focus_cycles:
                    data["focus_cycles"][str(focus_cycle.order)] = {
                        "type": focus_cycle.cycle_type,
                        "duration_seconds": focus_cycle.duration.seconds,
                        "is_completed": focus_cycle.is_completed,
                        "order": focus_cycle.order,
                    }
        return data

    async def change_cycle_if_needed(self):
        """
        never call this method directly from client, this is only for internal purpose
        to change the cycle if needed
        """
        current_cycle = await self._get_current_cycle()
        all_focus_period_duration = await self._get_all_focus_period_duration_for_current_cycle(current_cycle)
        if await self._is_cycle_transition_needed(current_cycle, all_focus_period_duration):
            await self._transition_to_next_cycle()

    async def _is_cycle_transition_needed(self, current_cycle, all_focus_period_duration):
        remaining_time = current_cycle.duration.seconds - all_focus_period_duration.seconds
        return remaining_time <= 0

    async def _transition_to_next_cycle(self):
        await self._save_last_focus_period_of_current_session()
        current_cycle = await self._get_current_cycle()
        current_cycle.is_completed = True
        await current_cycle.asave()
        next_cycles_qs = await database_sync_to_async(self.session.focus_cycles.filter)(  # type: ignore
            order__gt=current_cycle.order
        )
        next_cycle = await database_sync_to_async(next_cycles_qs.first)()
        if next_cycle:
            self.session.current_cycle = next_cycle
            await self.session.asave()
            # create a new focus period for the next cycle
            await database_sync_to_async(FocusPeriod.objects.create)(
                session=self.session,
                cycle=next_cycle,
            )
        else:
            # since there is no next cycle, we will stop the timer
            await self.stop_timer()


async def trigger_sync_inactive_timer_for_all_connected_clients(session_id: str):
    channel_layer = get_channel_layer()
    await channel_layer.group_send(  # type: ignore
        f"focus_session_{session_id}",
        {
            "type": "sync_inactive_timer",
        },
    )
