from django import template
from datetime import timedelta

register = template.Library()


@register.filter
def timeformat(td):
    if isinstance(td, timedelta):
        total_seconds = int(td.total_seconds())
        hours = total_seconds // 3600
        minutes = (total_seconds % 3600) // 60

        if hours > 0:
            return f"{hours} hour{'s' if hours != 1 else ''} {minutes} min{'s' if minutes != 1 else ''}"
        else:
            return f"{minutes} min{'s' if minutes != 1 else ''}"
    return str(td)
