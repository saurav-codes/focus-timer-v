from django import template
import json
from django.utils.safestring import SafeString
from datetime import date, datetime

register = template.Library()


def json_serial(obj):
    """JSON serializer for objects not serializable by default json code"""
    if isinstance(obj, (date, datetime)):
        return obj.isoformat()
    raise TypeError(f"Type {type(obj)} not serializable")


@register.filter
def jsonify(data, key=None):
    if isinstance(data, (list, tuple)):
        if key:
            return json.dumps(
                [item[key] if isinstance(item, dict) else str(item) for item in data], default=json_serial
            )
        else:
            return json.dumps([item for item in data], default=json_serial)
    elif isinstance(data, dict):
        return json.dumps(data.get(key, str(data)) if key else data, default=json_serial)
    else:
        return json.dumps(str(data))
