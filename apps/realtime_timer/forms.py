from re import I
from typing import Any
from .models import FocusSession, User
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


class ProfileForm(forms.ModelForm):
    """Form for updating user profile information."""
    
    class Meta:
        model = User
        fields = ['bio', 'long_term_goals', 'short_term_goals', 'timezone']
        widgets = {
            'bio': forms.Textarea(attrs={
                'rows': 4,
                'class': 'block w-full rounded-md border-gray-300 shadow-sm focus:border-blue-500 focus:ring-blue-500 sm:text-sm',
                'placeholder': 'Tell us about yourself, your work style, and preferences...'
            }),
            'long_term_goals': forms.Textarea(attrs={
                'rows': 3,
                'class': 'block w-full rounded-md border-gray-300 shadow-sm focus:border-blue-500 focus:ring-blue-500 sm:text-sm',
                'placeholder': 'What do you want to achieve in the next 6-12 months?'
            }),
            'short_term_goals': forms.Textarea(attrs={
                'rows': 3,
                'class': 'block w-full rounded-md border-gray-300 shadow-sm focus:border-blue-500 focus:ring-blue-500 sm:text-sm',
                'placeholder': 'What do you want to achieve in the next 1-3 months?'
            }),
            'timezone': forms.Select(attrs={
                'class': 'block w-full rounded-md border-gray-300 shadow-sm focus:border-blue-500 focus:ring-blue-500 sm:text-sm'
            })
        }

    def clean_bio(self):
        bio = self.cleaned_data['bio']
        if len(bio) > 1000:
            raise forms.ValidationError("Bio must be 1000 characters or less.")
        return bio

    def clean_long_term_goals(self):
        goals = self.cleaned_data['long_term_goals']
        if len(goals) > 1000:
            raise forms.ValidationError("Long term goals must be 1000 characters or less.")
        return goals

    def clean_short_term_goals(self):
        goals = self.cleaned_data['short_term_goals']
        if len(goals) > 1000:
            raise forms.ValidationError("Short term goals must be 1000 characters or less.")
        return goals
