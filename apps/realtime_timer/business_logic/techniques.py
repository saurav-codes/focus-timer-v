import datetime

from pytz import UTC
from ..models import FocusCycle, FocusSession


###############################################
# HELPER FUNCTIONS FOR GENERATING CAMEL FOCUS CYCLES
###############################################


def handle_distribute_extra_time_to_long_cycles(cycles, time_to_distribute):
    distributed = 0
    long_focus_indices = [i for i, duration in enumerate(cycles) if duration >= 50]
    for index in long_focus_indices:
        if distributed < time_to_distribute:
            cycles[index] += 1
            distributed += 1
        else:
            break
    return distributed


def handle_distribute_extra_time_to_short_cycles(cycles, time_to_distribute):
    # Keep track of how much time we've added
    time_added = 0

    # Go through each cycle, except the last four
    for i in range(len(cycles) - 4):
        # Check if this is a short focus period (25 minutes)
        if cycles[i] >= 25 and cycles[i] < 28:
            # If we haven't distributed all the time yet
            if time_added < time_to_distribute:
                # Add 1 minute to this short focus period
                cycles[i] += 1
                # Count that we've added a minute
                time_added += 1
            if time_added == time_to_distribute:
                # If we've distributed all the time, stop the loop
                break

    # Return how much time we actually added
    return time_added


def handle_distribute_extra_time_to_last_25_5_25_5_cycles(cycles, time_to_distribute):
    # Keep track of how much time we've added
    time_added = 0

    # The positions of the last two 25-minute focus periods
    # -4 means the fourth last item, -2 means the second last item
    last_short_focus_positions = [-4, -2]
    is_cycles_list_less_than_4_items = len(cycles) < 4

    # Go through the positions of the last two 25-minute periods
    for position in last_short_focus_positions:
        # If we haven't distributed all the time yet
        try:
            if time_added < time_to_distribute and cycles[position] < 28:
                # Add 1 minute to this 25-minute period
                cycles[position] += 1
                # Count that we've added a minute
                time_added += 1
        except IndexError:
            # this means that cycles list is shorter than 4 items,
            pass
        if time_added == time_to_distribute:
            # If we've distributed all the time, stop the loop
            break
    if is_cycles_list_less_than_4_items:
        # if cycles list is short and this function is called which means
        # user wants to distribute the extra time to the last 25-5-25-5 cycles
        # so we will distribute this time to whatever cycles are left
        for indx in range(len(cycles)):
            if time_added < time_to_distribute:
                cycles[indx] += 1
                time_added += 1

    # Return how much time we actually added
    return time_added


def get_distribution_functions(
    distribute_extra_time_to_long_cycles,
    distribute_extra_time_to_short_cycles,
    distribute_extra_time_to_last_25_5_25_5_cycles,
):
    distribution_functions = []
    if distribute_extra_time_to_long_cycles:
        distribution_functions.append(handle_distribute_extra_time_to_long_cycles)
    if distribute_extra_time_to_short_cycles:
        distribution_functions.append(handle_distribute_extra_time_to_short_cycles)
    if distribute_extra_time_to_last_25_5_25_5_cycles:
        distribution_functions.append(handle_distribute_extra_time_to_last_25_5_25_5_cycles)
    return distribution_functions


def get_possible_long_focus_durations_in_given_time(total_time):
    long_focus_durations = [50, 60, 70, 80, 90]
    possible_durations = []
    while total_time >= 90:  # 90 = 50 (shortest long focus) + 10 + 25 + 5
        for duration in long_focus_durations:
            if total_time >= duration + 10 + 25 + 5:
                possible_durations.append([duration, 10, 25, 5])
                total_time -= duration + 10 + 25 + 5
    return sorted(possible_durations, reverse=True)


# main function to generate Camel Techniques
def generate_camel_focus_cycles(
    total_time: int,
    distribute_extra_time_to_long_cycles: bool,
    distribute_extra_time_to_short_cycles: bool,
    distribute_extra_time_to_last_25_5_25_5_cycles: bool,
):
    """
    Generate focus cycles using the Camel Technique, correctly alternating between long and short focus cycles.

    Key features:
    1. Starts with longer focus cycles (90 minutes by default) that gradually decrease.
       but it will never go below 50 minutes and will never go above 95 minutes.
       and also it depends on the total time the user wants to focus. ideally
       it generates the long focus cylces like 50 60 or 90 but we can add extra
       time to the long focus cycles by distributing it to the long focus cycles
       and extend those long sessions upto +7 minutes max. so a 90 minutes cycle will
       be extended to 97 minutes max. also same way we can extend the short focus
       cycles upto +5 minutes max. but that max value for long and short focus can be
       CamelTechnique.get_long_focus_based_on_cycle_duration() +7 or
       CamelTechnique.get_short_focus_based_on_cycle_duration() +5
       also the distribution is controlled by distribute_extra_time_to_long_cycles: bool,
       distribute_extra_time_to_short_cycles: bool and distribute_extra_time_to_last_25_5_25_5_cycles: bool,
       if the user wants to distribute the extra time to the long focus cycles, short focus cycles
       or the final 25-5-25-5 cycles.

    2. Alternates between long and short (25-minute) focus cycles.
    3. Incorporates regular breaks (10 minutes after long focus cycles, 5 minutes after short focus cycles).
    4. Ends with a consistent pattern of 25-5-25-5 (minutes) for focus-break cycles but it's not always
       same pattern, for cases when we focus for less than 90 minutes, we will have
       [50,10,25,5]. here we only have 25-5 one time because there is no time left for the
       other 25-5 cycle.
    5. Adjusts to fit within the specified total time while maintaining the core structure.
    6. Distributes extra time based on user preferences.

    Args:
    total_hours (int): The total number of hours for the session.
    minutes (int): Additional minutes for the session.
    distribute_extra_time_to_long_cycles (bool): Distribute extra time to long focus cycles.
    distribute_extra_time_to_short_cycles (bool): Distribute extra time to short focus cycles.
    distribute_extra_time_to_last_25_5_25_5_cycles (bool): Distribute extra time to the final 25-5-25-5 cycles.
    user: The user object, used for timezone information.

    Returns:
    dict: A dictionary containing the generated cycles, total cycle count, and additional information.
    """

    if total_time < 30:
        return (
            [
                total_time,
            ],
            0,
            total_time,
        )

    cycles = []
    reserved_mins = False
    remaining_time = total_time
    if total_time > 60 and not (total_time <= 120):
        remaining_time -= 60
        reserved_mins = True
    possible_long_focus_durations = get_possible_long_focus_durations_in_given_time(remaining_time)

    for duration in possible_long_focus_durations:
        cycles.extend(duration)

    remaining_time -= sum(cycles)

    while remaining_time >= 30:
        cycles.extend([25, 5])
        remaining_time -= 30

    # also since we reserved 60 minutes for the 25-5-25-5 pattern, we need to add it to the cycles
    while reserved_mins:
        cycles.extend([25, 5, 25, 5])
        reserved_mins = False

    # now we need to distribute the remaining time to the cycles
    # based on the choosed distribution methods
    distribution_functions = get_distribution_functions(
        distribute_extra_time_to_long_cycles,
        distribute_extra_time_to_short_cycles,
        distribute_extra_time_to_last_25_5_25_5_cycles,
    )
    while remaining_time > 0 and distribution_functions:
        time_per_function = remaining_time // len(distribution_functions)
        for distributing_function in distribution_functions:
            if remaining_time > 0:
                distributed_time_by_this_func = distributing_function(cycles, time_per_function)
                remaining_time -= distributed_time_by_this_func
                if distributed_time_by_this_func == 0:
                    # this means that now this function can't distribute any more time
                    # because the rules inside the function are not met for the remaining time
                    distribution_functions.remove(distributing_function)

    total_cycles_duration = sum(cycles)
    return cycles, remaining_time, total_cycles_duration


def _convert_cycles_list_to_dict(cycles):
    """
    to keep things less complex we are only returning a list of
    session durations from `generate_camel_focus_cycles` function
    but we need to structure this list into a dictionary which also
    include which duration is a break and which duration is focus.
    it will also includes the ordering even though ordering is only
    required for a giving <input> element a name in frontend. so that
    every input tag with a duration have a unique name suffixed with
    order.
    """
    cycles_dict = []

    def get_cycle_type(indx):
        # 0 is focus, 1 is break, 2 is focus, 3 is break and so on
        return FocusCycle.FOCUS if indx % 2 == 0 else FocusCycle.BREAK

    for indx, cycle_duration in enumerate(cycles):
        cycles_dict.append(
            {
                "order": indx + 1,
                "type": get_cycle_type(indx),
                "duration": cycle_duration,
            }
        )
    return cycles_dict


def generate_focus_cycle_data_based_on_technique_and_duration(
    technique: str,
    total_time: int,
    distribute_extra_time_to_long_cycles: bool,
    distribute_extra_time_to_short_cycles: bool,
    distribute_extra_time_to_last_25_5_25_5_cycles: bool,
    user,
):
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
            ],
            "exact_time_after_finishing_all_cycles": "12:00 PM",
            "extra_time_left": 0,
            "total_minutes_distributed": 0,
        }
    """
    if technique == FocusSession.CAMEL_TECHNIQUE:
        focus_cycles, remaining_time, total_cycles_duration = generate_camel_focus_cycles(
            total_time,
            distribute_extra_time_to_long_cycles,
            distribute_extra_time_to_short_cycles,
            distribute_extra_time_to_last_25_5_25_5_cycles,
        )
        focus_cycles = _convert_cycles_list_to_dict(focus_cycles)
        exact_time_after_finishing_all_cycles = datetime.datetime.now(tz=UTC) + datetime.timedelta(
            minutes=total_cycles_duration
        )
        return {
            "total_cycles": len(focus_cycles),
            "cycles": focus_cycles,
            "exact_time_after_finishing_all_cycles": exact_time_after_finishing_all_cycles.isoformat(),
            "extra_time_left": remaining_time,
            "total_minutes_distributed": total_cycles_duration,
        }

    else:
        raise ValueError(f"Technique {technique} not supported")
