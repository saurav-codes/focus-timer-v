import logging
from django.core.exceptions import ObjectDoesNotExist


class CustomRequestFilter(logging.Filter):
    def filter(self, record):
        if hasattr(record, "request"):
            request = record.request  # type: ignore
            record.ip_address = request.META.get("REMOTE_ADDR", "-")
            record.device_type = request.META.get("HTTP_SEC_CH_UA_PLATFORM")
            try:
                # ex string - "Brave";v="129", "Not=A?Brand";v="8", "Chromium";v="129"
                record.browser = request.META.get("HTTP_SEC_CH_UA").split(";")[0]
            except AttributeError:
                record.browser = "-"
            try:
                record.user = request.user.username if request.user.is_authenticated else "unauthenticated"
            except (ObjectDoesNotExist, AttributeError):
                record.user = "unauthenticated"
            record.http_status = getattr(record, "status_code", "-")
        else:
            record.ip_address = "-"
            record.user = "-"
            record.device_type = "-"
            record.browser = "-"
            record.http_status = "-"
        return True
