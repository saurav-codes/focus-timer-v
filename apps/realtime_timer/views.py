from typing import Any
from django.http import HttpResponse, JsonResponse
from django.urls import reverse
from django.views import View
from django.views.generic import TemplateView
from django.contrib.auth.mixins import LoginRequiredMixin
from django.shortcuts import get_object_or_404, render
from django.db.models import Sum, Avg, Count
from django.utils import timezone
from datetime import timedelta
from asgiref.sync import async_to_sync
import logging

from apps.realtime_timer.models import FocusPeriod, FocusSession, Task
from .business_logic import selectors, techniques
from .forms import FocusSessionForm
from django_htmx.http import HttpResponseClientRedirect

from django.conf import settings


logger = logging.getLogger(__name__)


class SessionListView(LoginRequiredMixin, TemplateView):
    template_name = "realtime_timer/sessions_list.html"

    def get_context_data(self, **kwargs: Any) -> dict[str, Any]:
        context_data = super().get_context_data(**kwargs)
        context_data["user_sessions"] = FocusSession.objects.filter(owner=self.request.user)[:10]
        logger.info(
            f"SessionListView: Retrieved user sessions for session list by user: {self.request.user.get_username()}",
            extra={"request": self.request},
        )
        return context_data


class SessionFormView(LoginRequiredMixin, TemplateView):
    """
    Main Session Page from where user can set the timer
    """

    template_name = "realtime_timer/session_form.html"

    def get_context_data(self, **kwargs: Any) -> dict[str, Any]:
        context_data = super().get_context_data(**kwargs)
        context_data["focus_session_form"] = FocusSessionForm()
        logger.info(
            f"SessionFormView: Retrieved focus session form for session form page by user: {self.request.user.get_username()}",
            extra={"request": self.request},
        )
        return context_data


class SessionDetailView(View):
    def get(self, request, session_id):
        focus_session = get_object_or_404(FocusSession, session_id=session_id)
        if request.user.is_authenticated:
            will_finish_at = async_to_sync(selectors.get_session_will_finish_at_async)(session=focus_session)
            is_session_owner = focus_session.owner == request.user
            username = request.user.get_username()
            tasks = selectors.get_user_tasks(request.user)
            logger.info(
                f"SessionDetailView: Authenticated user {username} accessed session {session_id}",
                extra={"request": request},
            )
        else:
            will_finish_at = None
            is_session_owner = False
            # if user is not logged in, we will use look for username in session
            # since we store username in session storage when unauthenticated user
            # try to join the session
            username = request.session.get("username", None)
            tasks = None
            logger.info(f"SessionDetailView: Anonymous user accessed session {session_id}", extra={"request": request})

        return render(
            request,
            "realtime_timer/session_detail.html",
            {
                "focus_session": focus_session,
                "will_finish_at": will_finish_at,
                "is_session_owner": is_session_owner,
                "username": username,
                "debug": settings.DEBUG,
                "tasks": tasks,
            },
        )

    def post(self, request, session_id):
        """
        handle anonymous user
        """
        # TODO: sanitize username to avoid hackers
        username = request.POST.get("username", None)
        # check if username is already in session followers
        focus_session = get_object_or_404(FocusSession, session_id=session_id)
        if focus_session.followers.filter(username=username).exists():  # type: ignore
            # username is already in session followers
            # so we will redirect to session detail page
            logger.warning(
                f"SessionDetailView: Username {username} already in session {session_id}", extra={"request": request}
            )
            return HttpResponse("Username already in session", status=200)
        else:
            # save username in session storage
            request.session["username"] = username
            logger.info(
                f"SessionDetailView: Added username {username} to session {session_id}", extra={"request": request}
            )
        session_detail_url = reverse("realtime_timer:session-detail-view", args=[session_id])
        return HttpResponseClientRedirect(session_detail_url)


class LandingPageView(TemplateView):
    template_name = "realtime_timer/landing_page.html"


class DashboardView(LoginRequiredMixin, TemplateView):
    template_name = "realtime_timer/dashboard.html"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        dashboard_data = selectors.get_dashboard_data_for_user(self.request.user)
        context.update(dashboard_data)
        return context


def get_technique_info(request):
    technique = request.GET.get("technique")
    description = techniques.TECHNIQUE_DESCRIPTIONS.get(technique, "Description not available.")
    return JsonResponse({"description": description})
