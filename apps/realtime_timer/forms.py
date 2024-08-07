from .models import FocusSession
from django import forms


class FocusSessionForm(forms.ModelForm):
    distribute_extra_time_to_existing_focus_sessions = forms.BooleanField(required=False)

    class Meta:
        model = FocusSession
        fields = ["technique", "duration_hours", "duration_minutes", "distribute_extra_time_to_existing_focus_sessions"]
