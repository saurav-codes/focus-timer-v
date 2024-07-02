from django.shortcuts import render, redirect
from django.contrib.auth.decorators import login_required
from django.http import HttpResponse
from django.utils import timezone
from datetime import timedelta
from .models import FocusSession, FocusInterval, UserProfile, CustomTechnique


@login_required
def home(request):
    user_profile, created = UserProfile.objects.get_or_create(user=request.user)
    active_session = FocusSession.objects.filter(user=request.user, end_time__isnull=True).first()

    context = {
        "user_profile": user_profile,
        "active_session": active_session,
    }
    return render(request, "timer/home.html", context)


@login_required
def start_session(request):
    if request.method == "POST":
        technique = request.POST.get("technique")
        total_duration = timedelta(hours=int(request.POST.get("total_hours", 0)))

        session = FocusSession.objects.create(
            user=request.user,
            technique=technique,
            total_duration=total_duration,
            is_streamer_session=UserProfile.objects.get(user=request.user).is_streamer,
        )

        # Generate intervals based on the chosen technique
        generate_intervals(session)

        return redirect("active_session")

    return render(request, "timer/start_session.html")


@login_required
def active_session(request):
    session = FocusSession.objects.filter(user=request.user, end_time__isnull=True).first()
    if not session:
        return redirect("timer:home")

    current_interval = session.intervals.filter(end_time__isnull=True).first()

    context = {
        "session": session,
        "current_interval": current_interval,
        "session_progress": get_session_progress(session),
        "interval_progress": get_interval_progress(current_interval) if current_interval else 0,
    }
    return render(request, "timer/active_session.html", context)


@login_required
def end_session(request):
    session = FocusSession.objects.filter(user=request.user, end_time__isnull=True).first()
    if session:
        session.end_time = timezone.now()
        session.save()
        # End the last interval
        last_interval = session.intervals.filter(end_time__isnull=True).first()
        if last_interval:
            last_interval.end_time = timezone.now()
            last_interval.save()

    return redirect("home")


@login_required
def join_session(request, streamer_id):
    streamer_session = FocusSession.objects.filter(
        user_id=streamer_id, is_streamer_session=True, end_time__isnull=True
    ).first()

    if streamer_session:
        user_session = FocusSession.objects.create(
            user=request.user,
            technique=streamer_session.technique,
            total_duration=streamer_session.total_duration,
            is_streamer_session=False,
        )
        # Copy intervals from streamer's session
        for interval in streamer_session.intervals.all():
            FocusInterval.objects.create(
                session=user_session,
                start_time=interval.start_time,
                end_time=interval.end_time,
                is_break=interval.is_break,
            )
        return redirect("active_session")
    else:
        return HttpResponse("No active streamer session found.")


@login_required
def analytics(request):
    sessions = FocusSession.objects.filter(user=request.user)
    total_focus_time = sum((s.end_time - s.start_time for s in sessions if s.end_time), timedelta())

    context = {
        "total_focus_time": total_focus_time,
        "sessions": sessions,
    }
    return render(request, "timer/analytics.html", context)


def generate_intervals(session):
    total_duration = session.total_duration
    technique = session.technique

    if technique == "CAMEL":
        intervals = generate_camel_intervals(total_duration)
    elif technique == "POMODORO":
        intervals = generate_pomodoro_intervals(total_duration)
    elif technique in ["FLOW_2H", "FLOW_4H"]:
        flow_duration = timedelta(hours=2 if technique == "FLOW_2H" else 4)
        intervals = generate_flow_intervals(total_duration, flow_duration)
    elif technique == "CUSTOM":
        custom_technique = CustomTechnique.objects.get(user=session.user)
        intervals = generate_custom_intervals(total_duration, custom_technique)
    else:
        raise ValueError(f"Unknown technique: {technique}")

    start_time = timezone.now()
    for interval in intervals:
        FocusInterval.objects.create(
            session=session,
            start_time=start_time,
            end_time=start_time + interval["duration"],
            is_break=interval["is_break"],
        )
        start_time += interval["duration"]


def generate_camel_intervals(total_duration):
    intervals = []
    remaining_duration = total_duration
    cycle_duration = timedelta(minutes=130)  # 90 + 10 + 25 + 5

    while remaining_duration >= cycle_duration:
        intervals.extend(
            [
                {"duration": timedelta(minutes=90), "is_break": False},
                {"duration": timedelta(minutes=10), "is_break": True},
                {"duration": timedelta(minutes=25), "is_break": False},
                {"duration": timedelta(minutes=5), "is_break": True},
            ]
        )
        remaining_duration -= cycle_duration

    # Add any remaining time as a focus interval
    if remaining_duration > timedelta():
        intervals.append({"duration": remaining_duration, "is_break": False})

    return intervals


def generate_pomodoro_intervals(total_duration):
    intervals = []
    remaining_duration = total_duration
    cycle_duration = timedelta(minutes=30)  # 25 + 5

    while remaining_duration >= cycle_duration:
        intervals.extend(
            [
                {"duration": timedelta(minutes=25), "is_break": False},
                {"duration": timedelta(minutes=5), "is_break": True},
            ]
        )
        remaining_duration -= cycle_duration

    # Add any remaining time as a focus interval
    if remaining_duration > timedelta():
        intervals.append({"duration": remaining_duration, "is_break": False})

    return intervals


def generate_flow_intervals(total_duration, flow_duration):
    intervals = []
    remaining_duration = total_duration

    while remaining_duration >= flow_duration:
        intervals.extend(
            [
                {"duration": flow_duration, "is_break": False},
                {"duration": timedelta(minutes=15), "is_break": True},
            ]
        )
        remaining_duration -= flow_duration + timedelta(minutes=15)

    # Add any remaining time as a focus interval
    if remaining_duration > timedelta():
        intervals.append({"duration": remaining_duration, "is_break": False})

    return intervals


def generate_custom_intervals(total_duration, custom_technique):
    intervals = []
    remaining_duration = total_duration
    cycle_duration = custom_technique.focus_duration + custom_technique.break_duration

    while remaining_duration >= cycle_duration:
        intervals.extend(
            [
                {"duration": custom_technique.focus_duration, "is_break": False},
                {"duration": custom_technique.break_duration, "is_break": True},
            ]
        )
        remaining_duration -= cycle_duration

    # Add any remaining time as a focus interval
    if remaining_duration > timedelta():
        intervals.append({"duration": remaining_duration, "is_break": False})

    return intervals


@login_required
def toggle_theme(request):
    profile = UserProfile.objects.get(user=request.user)
    profile.theme_preference = "dark" if profile.theme_preference == "light" else "light"
    profile.save()
    return redirect(request.META.get("HTTP_REFERER", "home"))


@login_required
def custom_technique(request):
    if request.method == "POST":
        name = request.POST.get("name")
        focus_duration = timedelta(minutes=int(request.POST.get("focus_duration")))
        break_duration = timedelta(minutes=int(request.POST.get("break_duration")))

        CustomTechnique.objects.create(
            user=request.user, name=name, focus_duration=focus_duration, break_duration=break_duration
        )
        return redirect("home")

    return render(request, "timer/custom_technique.html")


def get_session_progress(session):
    total_duration = session.total_duration
    elapsed_time = timezone.now() - session.start_time
    progress = min(elapsed_time / total_duration, 1.0) * 100
    return progress


def get_interval_progress(interval):
    if interval.end_time:
        return 100
    elapsed_time = timezone.now() - interval.start_time
    total_duration = (
        interval.end_time - interval.start_time if interval.end_time else timedelta(hours=1)
    )  # Fallback duration
    progress = min(elapsed_time / total_duration, 1.0) * 100
    return progress


@login_required
def update_session(request):
    session = FocusSession.objects.filter(user=request.user, end_time__isnull=True).first()
    if not session:
        return HttpResponse("No active session")

    current_interval = session.intervals.filter(end_time__isnull=True).first()

    context = {
        "session": session,
        "current_interval": current_interval,
    }
    return render(request, "timer/update_session.html", context)
