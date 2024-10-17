import logging
from django.forms import ValidationError
from django.http import HttpRequest, HttpResponse

from apps.realtime_timer.business_logic import selectors
from apps.realtime_timer.business_logic.onesignal import send_onesignal_notification

from ..models import FocusPeriod, FocusSession, FocusCycle, FocusSessionFollower, User
from django.contrib.auth import get_user_model
from django.utils import timezone
from django.utils.dateparse import parse_datetime
from channels.db import database_sync_to_async
from django.db import transaction
from channels.layers import get_channel_layer

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
    FocusPeriod.objects.create(session=focus_session, cycle=first_cycle, user=owner)
    logger.info(
        f"{owner.username} Created first focus period for session ID: {focus_session.session_id} and user - {owner}"
    )
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
    def __init__(self, session_id: str, user, username: str) -> None:
        self.session_id = session_id
        self.user = user
        self.username = username
        logger.info(f"AsyncTimerService initialized for session ID: {session_id}, user: {user.username}")

    @database_sync_to_async
    def create_session_follower(self, session: FocusSession):
        with transaction.atomic():
            if self.user.is_authenticated:
                FocusSessionFollower.objects.get_or_create(
                    session=session,
                    user=self.user,
                    username=self.user.username,
                    user_type="authenticated",
                )
            else:
                FocusSessionFollower.objects.get_or_create(
                    session=session,
                    username=self.username,
                    user_type="guest",
                )

    @database_sync_to_async
    def delete_session_follower(self):
        FocusSessionFollower.objects.filter(
            session_id=self.session_id, username=self.user.username or self.username
        ).delete()
        logger.info(
            f"Removing user '{self.user.username or self.username}' from session '{self.session_id}' followers",
        )

    @database_sync_to_async
    def create_new_focus_period(self, session: FocusSession, current_cycle: FocusCycle):
        try:
            with transaction.atomic():
                logger.info(f"Starting create_new_focus_period for session {session.session_id}")
                logger.info(f"User: {self.user}, Username: {self.user.username}")

                new_period = FocusPeriod.objects.create(session=session, cycle=current_cycle, user=self.user)

                logger.info(f"Created new focus period: {new_period.id}")
                logger.info(
                    f"{self.user.username} Created new focus period for session ID: {session.session_id}, cycle ID: {current_cycle.pk} and user - {self.user}"
                )

            logger.info("Finished create_new_focus_period successfully")
        except Exception as e:
            logger.error(f"Error in create_new_focus_period: {str(e)}", exc_info=True)

    async def save_last_focus_period(self, current_session: FocusSession):
        """
        this function is used to end the last focus period of the current session
        it's used when the timer is paused or stopped or when the user is done with the current cycle
        so we save the time for the last focus period.
        """
        # get the last focus period
        last_focus_period = await selectors.get_last_focus_period_async(current_session)
        if last_focus_period and not last_focus_period.ended_at:
            # since we are going to write to db we need to get a locked row to avoid race condition
            last_focus_period = await selectors.get_last_focus_period_locked_async(current_session)
            # if the last focus period is not ended, end it
            last_focus_period.ended_at = timezone.now()
            # calculate the duration of the last focus period
            fp_duration = last_focus_period.ended_at - last_focus_period.started_at
            # when tab/browser sleeps & as they get active again, it's
            # more time passed already then it was in cycle.
            max_time_to_save_for_focus_period = await selectors.get_max_time_to_save_for_focus_period_async(
                current_cycle=current_session.current_cycle  # type: ignore
            )
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

    async def pause_timer(self, trigger_sync_timer=True):
        focus_session = await selectors.get_session_by_id_locked_async(self.session_id)
        if focus_session.timer_state == FocusSession.TIMER_RUNNING:
            logger.info(f"{self.user.username} Pausing timer for session ID: {focus_session.session_id}")
            focus_session.timer_state = FocusSession.TIMER_PAUSED
            await focus_session.asave(trigger_timer_sync=trigger_sync_timer)
            await self.save_last_focus_period(focus_session)

    async def stop_timer(self):
        """
        doesn't matter if the session is completed or not.
        we will just calculate all the time spent and end the last focus period
        and mark the session as completed
        """
        logger.info(f"{self.user.username} Stopping timer for session ID: {self.session_id}")
        await self.pause_timer(trigger_sync_timer=False)  # make sure the last focus period is ended
        session = await selectors.get_session_by_id_locked_async(self.session_id)
        await self.create_focus_periods_for_participants(session)
        session.total_focus_completed = await selectors.calculate_total_focus_completed_async(session)
        session.timer_state = FocusSession.TIMER_COMPLETED
        # syncing the timer after saving is neccessary so no choice here
        # other than direct passing trigger_timer_sync = True
        await session.asave(trigger_timer_sync=True)
        # Send notification when timer is completed
        message = "Congratulations! You've completed your focus session."
        await send_onesignal_notification(self.session_id, message)

    async def resume_timer(self):
        session = await selectors.get_session_by_id_locked_async(self.session_id)
        if session.timer_state == FocusSession.TIMER_PAUSED:
            # just add a new focus period
            current_cycle = await selectors.get_current_cycle_async(session)
            await self.create_new_focus_period(session, current_cycle)
            session.timer_state = FocusSession.TIMER_RUNNING
            await session.asave(trigger_timer_sync=True)
            logger.info(f"{self.user.username} Resumed timer for session ID: {session.session_id}")

    async def toggle_timer(self):
        logger.info(f"{self.user.username} Toggling timer for session ID: {self.session_id}")
        session = await selectors.get_session_by_id_async(self.session_id)
        if session.timer_state == FocusSession.TIMER_RUNNING:
            await self.pause_timer(trigger_sync_timer=True)
            return "paused"
        elif session.timer_state == FocusSession.TIMER_PAUSED:
            await self.resume_timer()
            return "resumed"

    async def schedule_only_first_cycle_change(self, redis_client):
        """
        This function is called to schedule the first cycle change
        after the timer is started
        """
        session = await selectors.get_session_by_id_async(self.session_id)
        if session.timer_state == FocusSession.TIMER_RUNNING:
            current_cycle = await selectors.get_current_cycle_async(session)
            session_owner = await selectors.get_session_owner_async(session)
            is_session_owner = self.user == session_owner
            if current_cycle.order == 1 and not current_cycle.is_scheduled and is_session_owner:
                logger.info(
                    f"Scheduling first cycle change for user '{self.user.username or self.username}' in session '{self.session_id}'",
                )
                # get the locked row of current cycle to avoid race condition
                current_cycle = await selectors.get_current_cycle_locked_async(session)
                all_focus_period_duration = await selectors.get_completed_fp_duration_for_current_cycle_async(
                    current_cycle
                )
                remaining_time = current_cycle.duration.seconds - all_focus_period_duration.seconds
                if remaining_time < 0:
                    remaining_time = 0
                    logger.info(
                        f"{self.user.username} first cycle is already completed and we are above the scheduled time, \
                            so we scheduling the current cycle to change right now",
                    )
                next_change_time = timezone.now() + timezone.timedelta(seconds=remaining_time)
                # first we need to check if there is already a scheduled change for this session
                await redis_client.zadd("scheduled_cycle_changes", {str(self.session_id): next_change_time.timestamp()})
                logger.info(
                    f"Scheduled first cycle change for user '{self.user.username}' in session '{self.session_id}' at {next_change_time}",
                )
                current_cycle.is_scheduled = True
                await current_cycle.asave()

    async def schedule_next_cycle_change(self, redis_client):
        session = await selectors.get_session_by_id_async(self.session_id)
        if session.timer_state == FocusSession.TIMER_RUNNING:
            current_cycle = await selectors.get_current_cycle_async(session)
            if current_cycle.is_scheduled:
                logger.info(
                    f"Not scheduling next cycle change for user '{self.user.username}' in session '{self.session_id}' because it's already scheduled"
                )
                return
            # get the locked row of current cycle to avoid race condition
            current_cycle = await selectors.get_current_cycle_locked_async(session)
            all_focus_period_duration = await selectors.get_completed_fp_duration_for_current_cycle_async(current_cycle)  # type: ignore
            remaining_time = current_cycle.duration.seconds - all_focus_period_duration.seconds  # type: ignore
            if remaining_time < 0:
                remaining_time = 0
                logger.info(
                    f"{self.user.username} cycle is already completed and we are above the scheduled time, \
                        so we scheduling the current cycle to change right now",
                )
            next_change_time = timezone.now() + timezone.timedelta(seconds=remaining_time)
            # first we need to check if there is already a scheduled change for this session
            await redis_client.zadd("scheduled_cycle_changes", {str(self.session_id): next_change_time.timestamp()})
            logger.info(
                f"Scheduled next cycle change for user '{self.user.username}' in session '{self.session_id}' at {next_change_time}",
            )
            current_cycle.is_scheduled = True
            await current_cycle.asave()
        else:
            logger.info(
                f"Not scheduling next cycle change for user '{self.user.username}' in session '{self.session_id}' because the timer is not running",
            )
            logger.warning(
                f"BUG: Timer is not running for session '{self.session_id}'. so find why this is happening",
                exc_info=True,
            )

    async def change_cycle_if_needed(self, session: FocusSession):
        """
        never call this method directly from client, this is only for internal purpose
        to change the cycle if needed
        """
        current_cycle = await selectors.get_current_cycle_async(session)
        all_focus_period_duration = await selectors.get_all_focus_period_duration_for_current_cycle_async(current_cycle)
        if await self._is_cycle_transition_needed(current_cycle, all_focus_period_duration):
            await self._transition_to_next_cycle()
            # Send notification when cycle changes
            focus_type = current_cycle.cycle_type.lower()
            message = f"Time's up! Your {focus_type} session has ended."
            await send_onesignal_notification(self.session_id, message)
            return True
        return False

    async def _is_cycle_transition_needed(self, current_cycle, all_focus_period_duration):
        remaining_time = current_cycle.duration.seconds - all_focus_period_duration.seconds
        return remaining_time <= 0

    async def cancel_scheduled_cycle_change_if_timer_stopped(self, redis_client, session_id: str):
        """
        This function will cancel the scheduled cycle change if the timer
        paused or stopped
        """
        session = await selectors.get_session_by_id_async(session_id)
        if session.timer_state != FocusSession.TIMER_RUNNING:
            # only cancel the scheduled cycle change if the timer is not running
            logger.info(f"Cancelling scheduled cycle change for session '{session_id}'")
            await redis_client.zrem("scheduled_cycle_changes", str(session_id))
            current_cycle = await selectors.get_current_cycle_locked_async(session)
            current_cycle.is_scheduled = False
            await current_cycle.asave()

    async def _transition_to_next_cycle(self):
        session = await selectors.get_session_by_id_async(self.session_id)
        await self.save_last_focus_period(session)
        logger.info("saved last focus session while changing cycle")
        current_cycle = await selectors.get_current_cycle_locked_async(session)
        logger.info(
            f"current cycle is duration - {current_cycle.duration}\
             & type - {current_cycle.cycle_type}\
             & order - {current_cycle.order}"
        )
        current_cycle.is_completed = True  # type: ignore
        logger.info("marked current cycle as completed")
        await current_cycle.asave()  # type: ignore
        next_cycles_qs = await database_sync_to_async(FocusCycle.objects.filter)(  # type: ignore
            order__gt=current_cycle.order, session=session  # type: ignore
        )
        next_cycle = await database_sync_to_async(next_cycles_qs.first)()
        if next_cycle:
            # get the locked row of session to avoid race condition
            # this increase the db query count because we are again
            # getting the session but it's okay for now because we
            # don't want any race conditions
            # TODO: find a better solution to avoid db query count increase
            session = await selectors.get_session_by_id_locked_async(self.session_id)
            session.current_cycle = next_cycle
            await session.asave(trigger_timer_sync=True)
            # create a new focus period for the next cycle
            await self.create_new_focus_period(session, next_cycle)
            logger.info(f"transitioned to next cycle with order - {next_cycle.order} & type - {next_cycle.cycle_type}")
            return True
        else:
            # since there is no next cycle, we will stop the timer
            await self.stop_timer()
            return False

    @database_sync_to_async
    def create_focus_periods_for_participants(self, session: FocusSession):
        logger.info(f"Creating focus periods for participants in session '{session.session_id}'")
        for user_id, periods in session.participant_data.items():
            user = User.objects.get(id=user_id)
            for period in periods:
                start_time = parse_datetime(period["join_at"])
                end_time = parse_datetime(period["leave_at"]) if period["leave_at"] else timezone.now()
                if start_time and end_time:
                    FocusPeriod.objects.create(
                        session=session,
                        user=user,
                        started_at=start_time,
                        ended_at=end_time,
                        duration=end_time - start_time,
                        cycle=session.current_cycle,  # this is just for avoid null error.. putting cycle here have no use
                    )
                    logger.info(
                        f"Created focus period for user '{user.username}' in session '{session.session_id}' as a participant"
                    )
                else:
                    logger.warning(
                        f"Invalid focus period data for user '{user.username}' in session '{session.session_id}': {period}"
                    )
        logger.info(f"finished creating focus periods for participants in session '{session.session_id}'")


async def trigger_sync_timer_for_all_connected_clients(session_id: str):
    channel_layer = get_channel_layer()
    await channel_layer.group_send(  # type: ignore
        f"focus_session_{session_id}",
        {
            "type": "sync_timer",
        },
    )
    logger.info(f"Triggered sync_timer for all connected clients for session ID: {session_id}")
