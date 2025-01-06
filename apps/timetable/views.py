import json

from django.http import HttpResponse, JsonResponse
from django.template.loader import render_to_string
from django.utils.decorators import method_decorator
from django.views import View
from django.views.decorators.csrf import csrf_protect
from django.views.generic import TemplateView

from ..realtime_timer.business_logic.selectors import get_focus_period_data_for_user
from .forms import TaskForm
from .types import ProductivityTechniques
from .utils import (
    fetch_user_todays_thoughts_and_tasks_dump_from_post_requests,
    generate_schedule_ai_gpt,
    update_schedule_with_changes,
)


class DayPlannerView(TemplateView):
    template_name = "timetable/day_planner.html"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['productivity_techniques'] = ProductivityTechniques.get_list_dict()
        return context

    def post(self, request, *args, **kwargs):
        user_todays_thoughts_and_tasks_dump = fetch_user_todays_thoughts_and_tasks_dump_from_post_requests(request)
        previous_schedule = get_focus_period_data_for_user(request.user)

        # Get selected techniques from the form
        selected_techniques = request.POST.getlist('techniques[]', [])

        generated_schedule = generate_schedule_ai_gpt(
            previous_schedule,
            {
                "long_term_goals": request.user.long_term_goals,
                "short_term_goals": request.user.short_term_goals,
                "bio": request.user.bio,
            },
            user_todays_thoughts_and_tasks_dump,
            techniques=selected_techniques
        )

        # Store the generated schedule in session for later updates
        request.session['current_schedule'] = generated_schedule

        # If it's an HTMX request, return only the partial
        if request.headers.get('HX-Request'):
            html = render_to_string(
                'timetable/partials/schedule_response.html',
                {'generated_schedule': generated_schedule}
            )
            return HttpResponse(html)

        # For regular POST requests, return the full page
        return self.render_to_response({
            'generated_schedule': generated_schedule
        })


@method_decorator(csrf_protect, name='dispatch')
class UpdateScheduleView(TemplateView):
    def post(self, request, *args, **kwargs):
        try:
            data = json.loads(request.body)
            updated_schedule = data.get('schedule', [])

            # Get the original schedule from session
            original_schedule = request.session.get('current_schedule', {})

            # Update the schedule using LangChain memory
            updated_data = update_schedule_with_changes(
                original_schedule=original_schedule,
                updated_items=updated_schedule,
                user_profile={
                    "long_term_goals": request.user.long_term_goals,
                    "short_term_goals": request.user.short_term_goals,
                    "bio": request.user.bio,
                }
            )

            # Store the updated schedule back in session
            request.session['current_schedule'] = updated_data

            return JsonResponse({'status': 'success', 'data': updated_data})
        except Exception as e:
            return JsonResponse({'status': 'error', 'message': str(e)}, status=400)


class TasksAddView(View):
    def post(self, request):
        try:

            data = json.loads(request.body)
            form = TaskForm(data)
            
            if form.is_valid():
                task = form.save(commit=False)
                task.user = request.user
                task.save()
                
                # Format time for response
                formatted_time = task.started_at.strftime("%H:%M")
                
                return JsonResponse({
                    'status': 'success',
                    'message': 'Task added successfully',
                    'task': {
                        'id': task.id,
                        'description': task.description,
                        'time': formatted_time
                    }
                })
            else:
                errors = []
                if 'description' in form.errors:
                    errors.append(form.errors['description'][0])
                if 'time' in form.errors:
                    errors.append(form.errors['time'][0])
                    
                return JsonResponse({
                    'status': 'error',
                    'message': ' '.join(errors)
                }, status=400)
                
        except Exception as e:
            return JsonResponse({
                'status': 'error',
                'message': str(e)
            }, status=400)


class CalendarView(TemplateView):
    template_name = "timetable/calendar.html"
