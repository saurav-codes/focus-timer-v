from django.shortcuts import render, redirect
from django.contrib.auth.decorators import login_required
from .models import Technique, Session, Interval
from django.utils import timezone


def homepage(request):
    return render(request, "realtime_timer/homepage.html")


@login_required
def start_session(request):
    if request.method == "POST":
        technique_id = request.POST.get("technique_id")
        total_duration = int(request.POST.get("total_duration"))  # in minutes

        technique = Technique.objects.get(id=technique_id)
        session = Session.objects.create(
            creator=request.user,
            technique=technique,
            total_duration=total_duration * 60,  # convert to seconds
            status="active",
        )

        # Create intervals based on the technique
        current_time = timezone.now()
        for pattern in technique.interval_patterns.order_by("order"):
            Interval.objects.create(
                session=session,
                start_time=current_time,
                is_focus=pattern.is_focus,
                duration=pattern.focus_duration if pattern.is_focus else pattern.break_duration,
            )
            current_time += timezone.timedelta(
                seconds=pattern.focus_duration if pattern.is_focus else pattern.break_duration
            )

        return redirect("active_session", session_id=session.id)

    techniques = Technique.objects.filter(is_custom=False)  # Only show predefined techniques for now
    return render(request, "realtime_timer/start_session.html", {"techniques": techniques})


@login_required
def active_session(request, session_id):
    session = Session.objects.get(id=session_id)
    return render(request, "realtime_timer/active_session.html", {"session": session})
