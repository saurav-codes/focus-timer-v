from typing import Any
from django.http import HttpResponse, JsonResponse
from django.urls import reverse
from django.views import View
from django.views.generic import TemplateView
from django.contrib.auth.mixins import LoginRequiredMixin
from django.shortcuts import get_object_or_404, render, redirect
from channels.layers import get_channel_layer
from asgiref.sync import async_to_sync
import logging

from apps.realtime_timer.models import FocusSession, FocusSessionFollower
from django.contrib import messages

from .business_logic import selectors
from .forms import FocusSessionForm
from django_htmx.http import HttpResponseClientRedirect

logger = logging.getLogger(__name__)


class HomepageView(LoginRequiredMixin, TemplateView):
    template_name = "realtime_timer/homepage.html"

    def get_context_data(self, **kwargs: Any) -> dict[str, Any]:
        context_data = super().get_context_data(**kwargs)
        context_data["user_sessions"] = FocusSession.objects.all()[:10]
        logger.info("HomepageView: Retrieved user sessions for homepage by user: %s", self.request.user.username)  # type: ignore
        return context_data


class MainSessionView(LoginRequiredMixin, TemplateView):
    """
    Main Session Page from where user can set the timer
    """

    template_name = "realtime_timer/main_session.html"

    def get_context_data(self, **kwargs: Any) -> dict[str, Any]:
        context_data = super().get_context_data(**kwargs)
        context_data["focus_session_form"] = FocusSessionForm()
        logger.info("MainSessionView: Retrieved focus session form for main session page by user: %s", self.request.user.username)  # type: ignore
        return context_data


class SessionDetailView(View):
    def get(self, request, session_id):
        focus_session = selectors.get_focus_session_by_id(session_id=session_id)
        if request.user.is_authenticated:
            will_finish_at = selectors.get_session_will_finish_at(request_user=request.user, session=focus_session)
            is_session_owner = focus_session.owner == request.user
            username = request.user.username
            logger.info(f"SessionDetailView: Authenticated user {username} accessed session {session_id}")
        else:
            will_finish_at = None
            is_session_owner = False
            # if user is not logged in, we will use look for username in session
            # since we store username in session storage when unauthenticated user
            # try to join the session
            username = request.session.get("username", None)
            logger.info(f"SessionDetailView: Anonymous user accessed session {session_id}")

        return render(
            request,
            "realtime_timer/session_detail.html",
            {
                "focus_session": focus_session,
                "will_finish_at": will_finish_at,
                "is_session_owner": is_session_owner,
                "username": username,
            },
        )

    def post(self, request, session_id):
        """
        handle anonymous user
        """
        # TODO: sanitize username to avoid hackers
        username = request.POST.get("username", None)
        # check if username is already in session followers
        focus_session = selectors.get_focus_session_by_id(session_id=session_id)
        if focus_session.followers.filter(username=username).exists():  # type: ignore
            # username is already in session followers
            # so we will redirect to session detail page
            logger.warning(f"SessionDetailView: Username {username} already in session {session_id}")
            return HttpResponse("Username already in session", status=200)
        else:
            # save username in session storage
            request.session["username"] = username
            logger.info(f"SessionDetailView: Added username {username} to session {session_id}")
        session_detail_url = reverse("realtime_timer:session-detail-view", args=[session_id])
        return HttpResponseClientRedirect(session_detail_url)


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
