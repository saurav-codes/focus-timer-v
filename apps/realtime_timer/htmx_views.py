"""
These views are specifically for HTMX
as they return response suitable for HTMX
"""
from django.http import HttpResponse
from django.shortcuts import render, get_object_or_404
from django.views.decorators.http import require_POST
from django.contrib.auth.decorators import login_required

from apps.realtime_timer.business_logic import selectors
from apps.realtime_timer.models import FocusSession, Task
from .business_logic import services, techniques
from .forms import FocusSessionForm
from django.urls import reverse
from django_htmx.http import HttpResponseClientRedirect


@require_POST
def temporary_focus_cycles_generator_view(request):
    """
    return focus cycles table based on user input time
    and technique. but these sessions are not saved to the database yet
    they are only generated in this view and user can edit them.
    """
    form = FocusSessionForm(request.POST)
    if form.is_valid():
        generated_focus_cycle_data = techniques.generate_focus_cycle_data_based_on_technique_and_duration(
            technique=form.cleaned_data["technique"],
            total_time=form.cleaned_data["duration_hours"] * 60 + form.cleaned_data["duration_minutes"],
            distribute_extra_time_to_long_cycles=form.cleaned_data["distribute_extra_time_to_long_cycles"],
            distribute_extra_time_to_short_cycles=form.cleaned_data["distribute_extra_time_to_short_cycles"],
            distribute_extra_time_to_last_25_5_25_5_cycles=form.cleaned_data[
                "distribute_extra_time_to_last_25_5_25_5_cycles"
            ],
        )
        return render(
            request,
            "realtime_timer/partials/_focus_session_form.html",
            {
                "focus_session_form": form,
                "generated_focus_cycle_data": generated_focus_cycle_data,
            },
        )
    return render(request, "realtime_timer/partials/_focus_session_form.html", {"focus_session_form": form})


@require_POST
def focus_cycles_and_session_create_view(request):
    """
    create focus cycles and session
    """
    form = FocusSessionForm(request.POST)
    fetched_focus_cycle_data_from_post_req = services.fetch_focus_cycles_data_from_post_request(request)
    if isinstance(fetched_focus_cycle_data_from_post_req, HttpResponse):
        # there was an error in the form of generated_focus_cycle_data
        # maybe user entered 0.1 instead of 1 or something like that
        return fetched_focus_cycle_data_from_post_req
    if form.is_valid():
        # create focus cycles and session
        focus_session = services.create_focus_cycles_and_session(
            form.cleaned_data,
            fetched_focus_cycle_data_from_post_req,
            owner=request.user,
        )
        if isinstance(focus_session, FocusSession):
            return HttpResponseClientRedirect(
                reverse("realtime_timer:session-detail-view", args=[focus_session.session_id])
            )
        else:
            # add error message to the form
            form.add_error(None, str(focus_session))

    return render(
        request,
        "realtime_timer/partials/_focus_session_form.html",
        {"focus_session_form": form, "generated_focus_cycle_data": fetched_focus_cycle_data_from_post_req},
    )


def add_cycle_to_cycle_table_view(request):
    new_cycle_index = int(request.GET.get("index", 0)) + 1
    return render(request, "realtime_timer/partials/_new_cycle_form.html", {"index": new_cycle_index})


@login_required
@require_POST
def create_task(request, session_id):
    session = get_object_or_404(FocusSession, session_id=session_id, owner=request.user)
    description = request.POST.get("description")
    Task.objects.create(user=request.user, session=session, description=description)
    tasks = selectors.get_user_tasks(request.user)
    return render(request, "realtime_timer/partials/_task_list.html", {"tasks": tasks, "focus_session": session})


@login_required
@require_POST
def toggle_task(request, task_id):
    task = get_object_or_404(Task, id=task_id, user=request.user)
    task.is_completed = not task.is_completed
    task.save()
    if task.is_completed:
        toast_message = "Congratulations! You have completed the task.🎉"
    else:
        toast_message = "You have undone the task.🔄"
    tasks = selectors.get_user_tasks(request.user)
    return render(
        request,
        "realtime_timer/partials/_task_list.html",
        {"tasks": tasks, "focus_session": task.session, "toast_message": toast_message},
    )
