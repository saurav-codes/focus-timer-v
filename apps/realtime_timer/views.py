from typing import Any
from django.http import HttpResponse, JsonResponse
from django.urls import reverse
from django.views import View
from django.views.generic import TemplateView
from django.contrib.auth.mixins import LoginRequiredMixin
from django.shortcuts import get_object_or_404, render, redirect
from channels.layers import get_channel_layer
from asgiref.sync import async_to_sync

from apps.realtime_timer.models import FocusSession
from django.contrib import messages

from .business_logic import selectors
from .forms import FocusSessionForm
from django_htmx.http import HttpResponseClientRedirect


class HomepageView(LoginRequiredMixin, TemplateView):
    template_name = "realtime_timer/homepage.html"

    def get_context_data(self, **kwargs: Any) -> dict[str, Any]:
        context_data = super().get_context_data(**kwargs)
        context_data["user_sessions"] = FocusSession.objects.all()[:10]
        return context_data


class MainSessionView(LoginRequiredMixin, TemplateView):
    """
    Main Session Page from where user can set the timer
    """

    template_name = "realtime_timer/main_session.html"

    def get_context_data(self, **kwargs: Any) -> dict[str, Any]:
        context_data = super().get_context_data(**kwargs)
        context_data["focus_session_form"] = FocusSessionForm()
        return context_data


class SessionDetailView(View):
    def get(self, request, session_id):
        focus_session = selectors.get_focus_session_by_id(session_id=session_id)
        if request.user.is_authenticated:
            will_finish_at = selectors.get_session_will_finish_at(request_user=request.user, session=focus_session)
            is_session_owner = focus_session.owner == request.user
            username = request.user.username
        else:
            will_finish_at = None
            is_session_owner = False
            # if user is not logged in, we will use look for username in session
            # since we store username in session storage when unauthenticated user
            # try to join the session
            username = request.session.get("username", None)

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
        username = request.POST.get("username", None)
        # check if username is already in session followers
        session_followers = selectors.get_focus_session_by_id(session_id=session_id).followers.keys()
        if username in session_followers:
            # username is already in session followers
            # so we will redirect to session detail page
            return HttpResponse("Username already in session", status=200)
        else:
            # save username in session storage
            request.session["username"] = username
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
