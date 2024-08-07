from typing import Any
from django.views import View
from django.views.generic import TemplateView, ListView
from django.contrib.auth.mixins import LoginRequiredMixin
from django.shortcuts import render, redirect
from django.http import HttpResponse

from apps.realtime_timer.business_logic import techniques
from .business_logic import services, selectors
from .forms import FocusSessionForm


class HomepageView(TemplateView):
    template_name = "realtime_timer/homepage.html"


class MainSessionView(LoginRequiredMixin, TemplateView):
    """
    Main Session Page from where user can set the timer
    """

    template_name = "realtime_timer/main_session.html"

    def get_context_data(self, **kwargs: Any) -> dict[str, Any]:
        context_data = super().get_context_data(**kwargs)
        context_data["focus_session_form"] = FocusSessionForm()
        return context_data


class SessionDetailView(LoginRequiredMixin, View):
    def get(self, request, session_id):
        focus_session = selectors.get_focus_session_by_id(session_id=session_id)
        return render(
            request,
            "realtime_timer/session_detail.html",
            {"focus_session": focus_session},
        )


class JoinSessionView(LoginRequiredMixin, View):
    def post(self, request, session_id):
        session = selectors.get_focus_session_by_id(session_id=session_id)
        services.join_session(follower=request.user, session=session)
        return redirect("session_detail", session_id=session_id)


class DashboardView(LoginRequiredMixin, ListView):
    template_name = "dashboard.html"
    context_object_name = "user_sessions"

    def get_queryset(self):
        return selectors.get_user_sessions(user=self.request.user)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["followed_sessions"] = selectors.get_followed_sessions(user=self.request.user)
        return context


class CreateTaskView(LoginRequiredMixin, View):
    def post(self, request):
        session_id = request.POST.get("session_id")
        description = request.POST.get("description")
        session = selectors.get_focus_session_by_id(session_id=session_id)
        task = services.create_task(session=session, description=description)
        return HttpResponse(
            f'<li hx-target="this" hx-swap="outerHTML" id="task-{task.pk}">{task.description} <button hx-post="/task/{task.pk}/toggle/">Toggle</button></li>'
        )


class ToggleTaskView(LoginRequiredMixin, View):
    def post(self, request, task_id):
        task = selectors.get_task_by_id(task_id=task_id)
        if request.user == task.session.owner:
            services.toggle_task(task=task)
            return HttpResponse(
                f'<li hx-target="this" hx-swap="outerHTML" id="task-{task.pk}">{task.description} <button hx-post="/task/{task.pk}/toggle/">Toggle</button></li>'
            )
        return HttpResponse("Unauthorized", status=403)
