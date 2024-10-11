from typing import Any
from django.http import HttpResponse
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

from apps.realtime_timer.models import FocusSession

from .business_logic import selectors
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
            f"SessionListView: Retrieved user sessions for session list by user: {self.request.user.username}",  # type: ignore
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
            f"SessionFormView: Retrieved focus session form for session form page by user: {self.request.user.username}",
            extra={"request": self.request},
        )
        return context_data


class SessionDetailView(View):
    def get(self, request, session_id):
        focus_session = get_object_or_404(FocusSession, session_id=session_id)
        if request.user.is_authenticated:
            will_finish_at = async_to_sync(selectors.get_session_will_finish_at_async)(session=focus_session)
            is_session_owner = focus_session.owner == request.user
            username = request.user.username
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
        user = self.request.user

        # Get user's sessions
        user_sessions = FocusSession.objects.filter(owner=user)

        # Calculate overall statistics
        total_focus_time = user_sessions.aggregate(total=Sum("total_focus_completed"))["total"] or timedelta()

        total_sessions = user_sessions.count()
        avg_session_length = user_sessions.aggregate(avg=Avg("total_focus_completed"))["avg"] or timedelta()

        # Get data for charts
        last_30_days = timezone.now() - timedelta(days=30)
        daily_focus_time = (
            user_sessions.filter(created_at__gte=last_30_days)
            .values("created_at__date")
            .annotate(total=Sum("total_focus_completed"))
            .order_by("created_at__date")
        )

        # Convert timedelta to minutes for easier charting
        daily_focus_time = [
            {"date": item["created_at__date"], "total": item["total"].total_seconds() / 60 if item["total"] else 0}
            for item in daily_focus_time
        ]

        technique_distribution = (
            user_sessions.values("technique").annotate(count=Count("session_id")).order_by("-count")
        )

        # Get recent sessions
        recent_sessions = user_sessions.order_by("-created_at")[:5]

        context.update(
            {
                "total_focus_time": total_focus_time,
                "total_sessions": total_sessions,
                "avg_session_length": avg_session_length,
                "daily_focus_time": daily_focus_time,
                "technique_distribution": list(technique_distribution),
                "recent_sessions": recent_sessions,
            }
        )

        return context
