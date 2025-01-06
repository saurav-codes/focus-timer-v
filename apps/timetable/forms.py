from django import forms
from apps.realtime_timer.models import Task
from datetime import datetime, time

class TaskForm(forms.ModelForm):
    time = forms.TimeField(required=True)
    
    class Meta:
        model = Task
        fields = ['description']
        
    def clean_description(self):
        description = self.cleaned_data['description']
        if len(description) > 255:
            raise forms.ValidationError("Task description cannot exceed 255 characters.")
        return description
    
    def clean_time(self):
        time_value = self.cleaned_data['time']
        if not isinstance(time_value, time):
            raise forms.ValidationError("Invalid time format. Please use HH:MM format.")
        return time_value
    
    def save(self, commit=True):
        task = super().save(commit=False)
        # Convert time to datetime for the started_at field
        task_time = self.cleaned_data['time']
        current_date = datetime.now().date()
        task.started_at = datetime.combine(current_date, task_time)
        if commit:
            task.save()
        return task
