import datetime
from ..models import FocusCycle, FocusSession


def generate_camel_technique_cycles(
    total_hours: int, minutes: int, distribute_extra_time_to_existing_focus_sessions: bool, user
) -> dict:
    """
    The new technique optimizes focus and productivity by combining different session
    lengths based on time management as mental fatigue increases. At the beginning
    of the day, you have much more clarity and can concentrate for a longer time.
    Interrupting this flow of concentration with a 50-minute session can reduce
    productivity, so it's important to work at a staggered rate.

    Hard Session (90 minutes):
    Start your study day with a burst of energy!
    Choose a challenging task to focus on for the next 90 minutes.
    During this time, put your mind at ease and give your full attention
    to completing the task at hand.

    Long Break (10 minutes):
    After the 90-minute session, reward yourself with a 10-minute break.
    Use this time to recharge and prepare for the next study session.

    Easy Session (25 minutes):
    Now, switch gears and tackle a shorter and simpler task.
    Since you've already completed a long session, this is your chance
    to stay focused on easier tasks while still being productive.
    Enjoy the satisfaction of accomplishing a task within just 25 minutes.

    Short Break (5 minutes):
    Take a quick 5-minute break to recharge and prepare for the next cycle.

    By alternating between longer and shorter sessions, you can enhance
    your concentration and productivity. As the study session progresses,
    it becomes easier because each Hard Session is reduced by 10 minutes.
    By the end of your session, you'll have successfully tackled both short
    and long tasks.

    The frequent breaks, both short and long, ensure that you optimize
    your productivity and stay refreshed throughout the process.
    """
    message = ""
    total_minutes = (total_hours * 60) + minutes
    cycles = []
    remaining_time = total_minutes
    cycle_count = 1

    focus_long = 90
    break_long = 10
    focus_short = 25
    break_short = 5
    min_focus_duration = 15

    while remaining_time > 0:
        # Long Focus Session
        if remaining_time >= focus_long:
            cycles.append({"order": cycle_count, "type": "FOCUS", "duration": focus_long})
            remaining_time -= focus_long
            cycle_count += 1
        elif remaining_time >= min_focus_duration:
            cycles.append({"order": cycle_count, "type": "FOCUS", "duration": remaining_time})
            remaining_time = 0
        else:
            break

        # Long Break
        if remaining_time >= break_long:
            cycles.append({"order": cycle_count, "type": "BREAK", "duration": break_long})
            remaining_time -= break_long
            cycle_count += 1
        elif remaining_time > 0:
            break

        # Short Focus Session
        if remaining_time >= focus_short:
            cycles.append({"order": cycle_count, "type": "FOCUS", "duration": focus_short})
            remaining_time -= focus_short
            cycle_count += 1
        elif remaining_time >= min_focus_duration:
            cycles.append({"order": cycle_count, "type": "FOCUS", "duration": remaining_time})
            remaining_time = 0
        else:
            break

        # Short Break
        if remaining_time >= break_short:
            cycles.append({"order": cycle_count, "type": "BREAK", "duration": break_short})
            remaining_time -= break_short
            cycle_count += 1
        elif remaining_time > 0:
            break

        focus_long = max(focus_long - 10, focus_short)

    if distribute_extra_time_to_existing_focus_sessions and remaining_time > 0:
        focus_cycles = [cycle for cycle in cycles if cycle["type"] == "FOCUS"]
        for i in range(remaining_time):
            focus_cycles[i % len(focus_cycles)]["duration"] += 1
        message = f"{remaining_time} minutes distributed to existing focus sessions because they were too short for a focus session & you also selected to distribute the extra time to existing focus sessions"

    # we also need to provide user at which time he will finish all the cycles
    # this is helpful because rn user is just generating the session and not saving it
    # so he can try with different duration and see at which time he will finish all the cycles
    total_cycles_time = sum([cycle["duration"] for cycle in cycles])
    exact_time_after_finishing_all_cycles = datetime.datetime.now(user.timezone) + datetime.timedelta(
        minutes=total_cycles_time
    )
    exact_time_after_finishing_all_cycles_in_12_hr_format = exact_time_after_finishing_all_cycles.strftime("%I:%M %p")

    return {
        "total_cycles": len(cycles),
        "cycles": cycles,
        "message": message,
        "exact_time_after_finishing_all_cycles": exact_time_after_finishing_all_cycles_in_12_hr_format,
    }


def generate_focus_cycle_data_based_on_technique_and_duration(
    technique: str,
    duration_hours: int,
    duration_minutes: int,
    distribute_extra_time_to_existing_focus_sessions: bool,
    user,
) -> dict:
    """
    Generate sessions based on the technique and duration
    sample output:
        {
            "total_cycles": 4,
            "cycles": [
                {"order": 1, "type": "FOCUS", "duration": 90},
                {"order": 2, "type": "BREAK", "duration": 10},
                {"order": 3, "type": "FOCUS", "duration": 25},
                {"order": 4, "type": "BREAK", "duration": 5}
            ]
        }
    """
    if technique == FocusSession.CAMEL_TECHNIQUE:
        return generate_camel_technique_cycles(
            duration_hours, duration_minutes, distribute_extra_time_to_existing_focus_sessions, user
        )
    else:
        raise ValueError(f"Technique {technique} not supported")
