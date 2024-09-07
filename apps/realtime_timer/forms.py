from re import I
from typing import Any
from .models import FocusSession
from django import forms


class FocusSessionForm(forms.ModelForm):
    duration_hours = forms.IntegerField(
        required=True,
        max_value=17,
        min_value=0,
        initial=1,
        help_text="How many hours you want to focus for this session",
    )
    duration_minutes = forms.IntegerField(
        required=True,
        max_value=59,
        min_value=0,
        initial=0,
        help_text="How many minutes you want to focus for this session",
    )
    distribute_extra_time_to_long_cycles = forms.BooleanField(
        required=False, help_text="If you want to distribute the extra time to long cycles"
    )
    distribute_extra_time_to_short_cycles = forms.BooleanField(
        required=False, help_text="If you want to distribute the extra time to short cycles"
    )
    distribute_extra_time_to_last_25_5_25_5_cycles = forms.BooleanField(
        required=False, help_text="If you want to distribute the extra time to the last 25/5/25/5 cycles"
    )

    class Meta:
        model = FocusSession
        fields = [
            "technique",
            "duration_hours",
            "duration_minutes",
            "distribute_extra_time_to_long_cycles",
            "distribute_extra_time_to_short_cycles",
            "distribute_extra_time_to_last_25_5_25_5_cycles",
        ]

    def clean_duration_hours(self) -> int:
        duration_hours = self.cleaned_data["duration_hours"]
        if not isinstance(duration_hours, int):
            raise forms.ValidationError("Duration hours must be an integer like 1, 2, ... upto 17")
        return duration_hours

    def clean_duration_minutes(self) -> int:
        duration_minutes = self.cleaned_data["duration_minutes"]
        if not isinstance(duration_minutes, int):
            raise forms.ValidationError("Duration minutes must be an integer like 0, 15, 30, 45")
        return duration_minutes
