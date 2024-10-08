from django.http import HttpRequest
import json
from channels.db import database_sync_to_async
from .models import FocusSession
import logging
from functools import wraps


logger = logging.getLogger(__name__)


def generate_request_metadata(scope, user):
    request = HttpRequest()
    user_agent = str(scope["headers"][4][1].strip())
    try:
        ip_add = scope["client"][0]
    except Exception:
        ip_add = "-"
    try:
        user_os = user_agent.rsplit("(")[1].split(";")[0]
    except Exception:
        user_os = "-"
    request.META = {
        "REMOTE_ADDR": ip_add,
        "HTTP_SEC_CH_UA_PLATFORM": user_os,
    }
    request.user = user
    return request


def check_session_owner_async(func):
    """
    Decorator to check if the user is the session owner
    & if not, send an error message to the client
    because only session owner can perform this action
    """

    @wraps(func)
    async def wrapper(self, *args, **kwargs):
        user = self.scope["user"]

        @database_sync_to_async
        def get_session_owner():
            session = FocusSession.objects.get(session_id=self.session_id)
            return session.owner

        session_owner = await get_session_owner()

        if user != session_owner:
            logger.info(
                f"{user.username} tried to perform an action on session '{self.session_id}' but was not authorized"
            )
            await self.send(text_data=json.dumps({"error": "You are not authorized to perform this action."}))

        return await func(self, *args, **kwargs)

    return wrapper


# def check_internal_action_async(func):
#     """
#     Decorator to check if the action is performed by an internal action
#     it should never be called by a client so the goal of this decorator
#     is to make sure that this action is never called by a client
#     """

#     @wraps(func)
#     async def wrapper(self, *args, **kwargs):
#         user = self.scope["user"]
#         text_data = json.loads(args[0])
#         secret_key = text_data.get("secret_key")
#         if secret_key != settings.CYCLE_CHANGE_INTERNAL_SECRET_KEY:
#             logger.info(
#                 f"{user.username} tried to perform an internal action on session '{self.session_id}' but was not authorized"
#             )
#             await self.send(text_data=json.dumps({"error": "this action is restricted to the system."}))

#         return await func(self, *args, **kwargs)

#     return wrapper
