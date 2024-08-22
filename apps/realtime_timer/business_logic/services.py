from django.forms import ValidationError
from django.http import HttpRequest, HttpResponse
from ..models import FocusPeriod, FocusSession, FocusCycle
from django.contrib.auth import get_user_model
from django.db.models import Sum
from django.utils import timezone
from channels.db import database_sync_to_async

User = get_user_model()


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
    total_time_to_focus = focus_session_form_cleaned_data["total_time_to_focus"]
    focus_session = FocusSession.objects.create(
        owner=owner,
        technique=focus_session_form_cleaned_data["technique"],
        total_time_to_focus=timezone.timedelta(total_time_to_focus),
    )

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
        # except the value error from the duration field
        except ValidationError as e:
            focus_session.delete()
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

    # create first focus period because the focus session is started.
    FocusPeriod.objects.create(session=focus_session, cycle=first_cycle)
    return focus_session


def fetch_focus_cycles_data_from_post_request(request: HttpRequest) -> dict | HttpResponse:
    cycles_types = request.POST.getlist("focus_cycle_type")
    cycles_durations = request.POST.getlist("focus_cycle_duration")
    try:
        return {
            i: {"type": t, "duration": int(d)} for i, (t, d) in enumerate(zip(cycles_types, cycles_durations), start=1)
        }
    except ValueError:
        return HttpResponse(
            "Duration must be an integer like 1, 2, ... upto any number of minutes you want to focus or break"
        )


class AsyncTimerService:
    def __init__(self, session: FocusSession) -> None:
        self.session = session

    @database_sync_to_async
    def _get_timer_state(self):
        return self.session.timer_state

    @database_sync_to_async
    def _get_current_cycle(self):
        return FocusCycle.objects.get(id=self.session.current_cycle_id)  # type: ignore

    async def _create_new_focus_period(self):
        current_cycle = await self._get_current_cycle()
        await database_sync_to_async(FocusPeriod.objects.create)(session=self.session, cycle=current_cycle)

    @database_sync_to_async
    def _get_all_focus_period_duration_for_current_cycle(self, current_cycle) -> timezone.timedelta:
        total_time_focused_for_finished_fp = (
            FocusPeriod.objects.filter(
                cycle=current_cycle,
                ended_at__isnull=False,
            )
            .only("duration")
            .aggregate(total_time_focused=Sum("duration"))["total_time_focused"]
        )
        if not total_time_focused_for_finished_fp:
            # this means that this session is just started which is why it doesn't have
            # any finished sessions yet so we set an 0 timedelta so that it doesn't give
            # any error in calculations
            total_time_focused_for_finished_fp = timezone.timedelta(0)
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
        return duration_for_unfinished_fp + total_time_focused_for_finished_fp

    @database_sync_to_async
    def _save_last_focus_period_of_current_session(self):
        """
        this function is used to end the last focus period of the current session
        it's used when the timer is paused or stopped or when the user is done with the current cycle
        so we save the time for the last focus period.
        """
        # get the last focus period
        last_focus_period = self.session.focus_periods.last()  # type:ignore
        if last_focus_period and not last_focus_period.ended_at:
            # if the last focus period is not ended, end it
            last_focus_period.ended_at = timezone.now()
            last_focus_period.duration = last_focus_period.ended_at - last_focus_period.started_at
            last_focus_period.save()
            print(
                "last focus period ended with duration: ", last_focus_period.duration, "and id: ", last_focus_period.id
            )

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
            print("timer is running so pausing timer")
            self.session.timer_state = FocusSession.TIMER_PAUSED
            await self.session.asave()
            await self._save_last_focus_period_of_current_session()

    async def stop_timer(self):
        """
        doesn't matter if the session is completed or not.
        we will just calculate all the time spent and end the last focus period
        and mark the session as completed
        """
        await self.pause_timer()  # make sure the last focus period is ended
        self.session.total_focus_completed = await self._calculate_total_focus_completed()
        self.session.timer_state = FocusSession.TIMER_COMPLETED
        await self.session.asave()

    async def resume_timer(self):
        if self.session.timer_state == FocusSession.TIMER_PAUSED:
            print("timer is paused so resuming it")
            # just add a new focus period
            await self._create_new_focus_period()
            self.session.timer_state = FocusSession.TIMER_RUNNING
            await self.session.asave()

    async def toggle_timer(self):
        timer_state = await self._get_timer_state()
        if timer_state == FocusSession.TIMER_RUNNING:
            await self.pause_timer()
        elif timer_state == FocusSession.TIMER_PAUSED:
            await self.resume_timer()

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
                data["remaining_time"] = current_cycle.duration.seconds - all_focus_period_duration.seconds
                data["current_cycle"] = {
                    "type": current_cycle.cycle_type,
                    "order": current_cycle.order,
                    "duration_seconds": current_cycle.duration.seconds,
                }
                # also add remaining cycles data
                focus_cycles = await database_sync_to_async(list)(
                    self.session.focus_cycles.all()
                )  # get all cycles after current one
                for focus_cycle in focus_cycles:
                    data["focus_cycles"][str(focus_cycle.order)] = {
                        "type": focus_cycle.cycle_type,
                        "duration_seconds": focus_cycle.duration.seconds,
                        "is_completed": focus_cycle.is_completed,
                        "order": focus_cycle.order,
                    }
        return data

    async def transition_to_next_cycle(self):
        """
        here we invalidate the cache when"""
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
