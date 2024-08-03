from django.contrib.auth.views import TemplateView


class HomepageView(TemplateView):
    template_name = "realtime_timer/homepage.html"
