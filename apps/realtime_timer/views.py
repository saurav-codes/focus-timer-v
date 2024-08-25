from typing import Any
from django.views import View
from django.views.generic import TemplateView
from django.contrib.auth.mixins import LoginRequiredMixin
from django.shortcuts import get_object_or_404, render, redirect
from channels.layers import get_channel_layer
from asgiref.sync import async_to_sync

from apps.realtime_timer.models import FocusSession, SessionFollower

from .business_logic import selectors
from .forms import FocusSessionForm


class HomepageView(LoginRequiredMixin, TemplateView):
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
        is_session_owner = focus_session.owner == request.user
        followers = selectors.get_session_followers(session=focus_session)
        is_session_follower = selectors.is_user_a_session_follower(session=focus_session, user=request.user)
        will_finish_at = selectors.get_session_will_finish_at(request_user=request.user, session=focus_session)
        return render(
            request,
            "realtime_timer/session_detail.html",
            {
                "focus_session": focus_session,
                "followers": followers,
                "will_finish_at": will_finish_at,
                "is_session_owner": is_session_owner,
                "is_session_follower": is_session_follower,
            },
        )


class JoinSessionView(LoginRequiredMixin, View):
    def post(self, request, session_id):
        session = get_object_or_404(FocusSession, session_id=session_id)
        SessionFollower.objects.get_or_create(follower=request.user, session=session)
        # Trigger follower update
        channel_layer = get_channel_layer()
        async_to_sync(channel_layer.group_send)(  # type: ignore
            f"focus_session_{session_id}", {"type": "followers_update"}
        )
        return redirect("realtime_timer:session-detail-view", session_id=session_id)


# class DashboardView(LoginRequiredMixin, ListView):
#     template_name = "dashboard.html"
#     context_object_name = "user_sessions"

#     def get_queryset(self):
#         return selectors.get_user_sessions(user=self.request.user)

#     def get_context_data(self, **kwargs):
#         context = super().get_context_data(**kwargs)
#         context["followed_sessions"] = selectors.get_followed_sessions(user=self.request.user)
#         return context


# class CreateTaskView(LoginRequiredMixin, View):
#     def post(self, request):
#         session_id = request.POST.get("session_id")
#         description = request.POST.get("description")
#         session = selectors.get_focus_session_by_id(session_id=session_id)
#         task = services.create_task(session=session, description=description)
#         return HttpResponse(
#             f'<li hx-target="this" hx-swap="outerHTML" id="task-{task.pk}">{task.description} <button hx-post="/task/{task.pk}/toggle/">Toggle</button></li>'
#         )


# class ToggleTaskView(LoginRequiredMixin, View):
#     def post(self, request, task_id):
#         task = selectors.get_task_by_id(task_id=task_id)
#         if request.user == task.session.owner:
#             services.toggle_task(task=task)
#             return HttpResponse(
#                 f'<li hx-target="this" hx-swap="outerHTML" id="task-{task.pk}">{task.description} <button hx-post="/task/{task.pk}/toggle/">Toggle</button></li>'
#             )
#         return HttpResponse("Unauthorized", status=403)
