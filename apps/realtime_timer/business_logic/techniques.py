import datetime

from pytz import UTC
from django.utils.safestring import mark_safe
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

    return cycles, remaining_time


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


def generate_pomodoro_cycles(total_time):
    cycles = []
    while total_time >= 30:
        cycles.extend([25, 5])
        total_time -= 30
    return cycles, total_time


def generate_52_17_cycles(total_time):
    cycles = []
    while total_time >= 69:
        cycles.extend([52, 17])
        total_time -= 69
    return cycles, total_time


def generate_90_minute_cycles(total_time):
    cycles = []
    while total_time >= 100:
        cycles.extend([90, 10])
        total_time -= 100
    return cycles, total_time


def generate_2_hour_cycles(total_time):
    cycles = []
    while total_time >= 130:
        cycles.extend([120, 10])
        total_time -= 130
    return cycles, total_time


def generate_flowtime_cycles(total_time):
    cycles = []
    remaining_time = total_time
    focus_duration = 120  # Start with 2-hour focus periods
    break_duration = 30  # 30-minute breaks

    while remaining_time >= (focus_duration + break_duration):
        cycles.extend([focus_duration, break_duration])
        remaining_time -= focus_duration + break_duration

    # If there's time left for at least a 25-minute focus period, add it
    if remaining_time >= 25:
        cycles.append(remaining_time)
        remaining_time -= remaining_time

    return cycles, remaining_time


# Add this constant at the top of the file, after imports
TECHNIQUE_DESCRIPTIONS = {
    FocusSession.CAMEL_TECHNIQUE: mark_safe(
        """
    <h3>Camel Technique</h3>
        <p>The Camel Technique is a focus method that alternates between longer and shorter work periods, mimicking a camel's humps. It typically starts with a longer focus session (e.g., 90 minutes), followed by a short break, then a shorter focus session (e.g., 25 minutes), and another break.</p>
        <p>This technique was developed to leverage the natural ebb and flow of human attention spans, allowing for deep work during longer sessions and quick bursts of productivity during shorter ones.</p>
        <p>Benefits include:</p>
        <ul>
            <li>Balances intense focus with regular breaks</li>
            <li>Adapts to different types of tasks</li>
            <li>Helps maintain energy throughout the day</li>
        </ul>
        <p>You can read more about this technique <a class="text-blue-400" href="https://www.twitch.tv/vanyastudytogether/about" target="_blank">here</a></p>
    """
    ),
    FocusSession.POMODORO_TECHNIQUE: mark_safe(
        """
        <h3>Pomodoro Technique</h3>
        <p>The Pomodoro Technique, developed by Francesco Cirillo in the late 1980s, uses a timer to break work into intervals, traditionally 25 minutes in length, separated by short breaks.</p>
        <p>This technique is named after the tomato-shaped kitchen timer that Cirillo used as a university student. ("Pomodoro" is Italian for tomato.)</p>
        <p>Benefits include:</p>
        <ul>
            <li>Improves focus and concentration</li>
            <li>Reduces mental fatigue</li>
            <li>Increases accountability and motivation</li>
        </ul>
        <p>Learn more about the Pomodoro Technique <a class="text-blue-400" href="https://en.wikipedia.org/wiki/Pomodoro_Technique" target="_blank">here</a>.</p>
    """
    ),
    FocusSession.FOCUS_52_17_TECHNIQUE: mark_safe(
        """
        <h3>52/17 Method</h3>
        <p>The 52/17 method suggests working for 52 minutes followed by a 17-minute break. This technique was discovered by analyzing the habits of the most productive employees using a time-tracking app called DeskTime.</p>
        <p>The idea is to work with intense focus for about an hour and then take a substantial break to recharge.</p>
        <p>Benefits include:</p>
        <ul>
            <li>Promotes high-intensity focus</li>
            <li>Allows for proper mental recovery</li>
            <li>Helps maintain high productivity throughout the day</li>
        </ul>
        <p>Read more about the 52/17 method <a class="text-blue-400" href="https://www.themuse.com/advice/the-rule-of-52-and-17-its-random-but-it-ups-your-productivity" target="_blank">here</a>.</p>
    """
    ),
    FocusSession.FOCUS_90_TECHNIQUE: mark_safe(
        """
        <h3>90-Minute Focus Sessions</h3>
        <p>The 90-minute focus technique is based on the body's natural rhythm called the ultradian rhythm. This rhythm suggests that our minds can focus intensely for about 90 minutes before needing a break.</p>
        <p>This method was popularized by researchers at Florida State University, who found that elite performers tend to work in focused 90-minute sessions.</p>
        <p>Benefits include:</p>
        <ul>
            <li>Aligns with the body's natural energy cycles</li>
            <li>Allows for deep, focused work</li>
            <li>Promotes better work-life balance</li>
        </ul>
        <p>Discover more about this <a class="text-blue-400" href="https://blog.macaw-app.com/hack-your-focus-master-the-90-minute-rhythm-for-productivity-and-wellbeing/" target="_blank">here</a>.</p>
    """
    ),
    FocusSession.FOCUS_2_HOURS_TECHNIQUE: mark_safe(
        """
        <h3>2-Hour Focus Blocks</h3>
        <p>The 2-hour focus block technique involves dedicating larger chunks of uninterrupted time to deep work. This method is often used by professionals who need extended periods of concentration for complex tasks.</p>
        <p>While not attributed to a specific person, this technique is popular among writers, programmers, and other creative professionals who benefit from long stretches of focused work.</p>
        <p>Benefits include:</p>
        <ul>
            <li>Ideal for complex, creative tasks</li>
            <li>Reduces context-switching</li>
            <li>Allows for achieving a state of 'flow'</li>
        </ul>
        <p>Learn more about deep work and extended focus sessions <a class="text-blue-400" href="https://en.wikipedia.org/wiki/Flow_(psychology)" target="_blank">here</a>.</p>
    """
    ),
    FocusSession.FLOWTIME_TECHNIQUE: mark_safe(
        """
        <h3>Flowtime Technique</h3>
        <p>The Flowtime Technique is a flexible focus method that allows you to work for as long as you can maintain focus, followed by a break proportional to your work time. It was developed as an alternative to rigid time-boxing methods.</p>
        <p>This technique encourages you to listen to your body and mind, working when you're in the flow and taking breaks when needed.</p>
        <p>Benefits include:</p>
        <ul>
            <li>Adapts to personal energy levels and focus capacity</li>
            <li>Reduces pressure of fixed time intervals</li>
            <li>Encourages self-awareness and productivity tracking</li>
        </ul>
        <p>Explore more about the Flowtime Technique <a class="text-blue-400" href="https://medium.com/@lightsonsoftware/the-flowtime-technique-7685101bd191" target="_blank">here</a>.</p>
    """
    ),
    FocusSession.CUSTOM_TECHNIQUE: mark_safe(
        """
        <h3>Custom Technique</h3>
        <p>The Custom Technique allows you to create your own focus and break patterns tailored to your specific needs and preferences.</p>
        <p>This flexibility is perfect for those who have found that standard techniques don't quite fit their work style or for tasks that require a unique approach.</p>
        <p>Benefits include:</p>
        <ul>
            <li>Fully customizable to your needs</li>
            <li>Can be adapted for different types of tasks</li>
            <li>Allows for experimentation to find your optimal work rhythm</li>
        </ul>
        <p>Learn about various productivity techniques <a class="text-blue-400" href="https://en.wikipedia.org/wiki/Time_management" target="_blank">here</a>.</p>
    """
    ),
}


# Modify the generate_focus_cycle_data_based_on_technique_and_duration function
def generate_focus_cycle_data_based_on_technique_and_duration(
    technique: str,
    total_time: int,
    distribute_extra_time_to_long_cycles: bool,
    distribute_extra_time_to_short_cycles: bool,
    distribute_extra_time_to_last_25_5_25_5_cycles: bool,
):
    if technique == FocusSession.CAMEL_TECHNIQUE:
        focus_cycles, remaining_time = generate_camel_focus_cycles(
            total_time,
            distribute_extra_time_to_long_cycles,
            distribute_extra_time_to_short_cycles,
            distribute_extra_time_to_last_25_5_25_5_cycles,
        )
    elif technique == FocusSession.POMODORO_TECHNIQUE:
        focus_cycles, remaining_time = generate_pomodoro_cycles(total_time)
    elif technique == FocusSession.FOCUS_52_17_TECHNIQUE:
        focus_cycles, remaining_time = generate_52_17_cycles(total_time)
    elif technique == FocusSession.FOCUS_90_TECHNIQUE:
        focus_cycles, remaining_time = generate_90_minute_cycles(total_time)
    elif technique == FocusSession.FOCUS_2_HOURS_TECHNIQUE:
        focus_cycles, remaining_time = generate_2_hour_cycles(total_time)
    elif technique == FocusSession.FLOWTIME_TECHNIQUE:
        focus_cycles, remaining_time = generate_flowtime_cycles(total_time)
    elif technique == FocusSession.CUSTOM_TECHNIQUE:
        focus_cycles = [total_time]
        remaining_time = 0
    else:
        raise ValueError(f"Technique {technique} not supported")

    total_cycles_duration = sum(focus_cycles)
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
        "technique_description": TECHNIQUE_DESCRIPTIONS.get(technique),
    }
