from django.forms import ValidationError
from django.http import HttpRequest
from django.utils import timezone
from ..models import FocusSession, FocusCycle, Task, SessionFollower
from django.contrib.auth import get_user_model

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
    focus_session = FocusSession.objects.create(
        owner=owner,
        technique=focus_session_form_cleaned_data["technique"],
        duration_hours=focus_session_form_cleaned_data["duration_hours"],
        duration_minutes=focus_session_form_cleaned_data["duration_minutes"],
    )

    # Create focus cycles
    for order, cycle_data in fetched_focus_cycle_data_from_post_request.items():
        try:
            fc = FocusCycle(
                session=focus_session,
                cycle_type=cycle_data["type"],
                duration=cycle_data["duration"],
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
    first_cycle = focus_session.focus_cycles.first()
    if first_cycle:
        focus_session.current_cycle = first_cycle
        focus_session.save()

    return focus_session


def pause_timer(*, session: FocusSession) -> None:
    if session.is_running:
        session.total_focus_time += timezone.now() - session.timer_start
        session.is_running = False
        session.save()


def stop_timer(*, session: FocusSession) -> None:
    if session.is_running:
        pause_timer(session=session)
    session.is_completed = True
    session.save()


def create_task(*, session: FocusSession, description: str) -> Task:
    return Task.objects.create(session=session, description=description)


def toggle_task(*, task: Task) -> None:
    task.is_completed = not task.is_completed
    task.save()


def join_session(*, follower, session: FocusSession) -> SessionFollower:
    return SessionFollower.objects.get_or_create(follower=follower, session=session)[0]


def fetch_focus_cycles_data_from_post_request(request: HttpRequest) -> dict:
    cycles_types = request.POST.getlist("focus_cycle_type")
    cycles_durations = request.POST.getlist("focus_cycle_duration")
    return {i: {"type": t, "duration": int(d)} for i, (t, d) in enumerate(zip(cycles_types, cycles_durations), start=1)}
