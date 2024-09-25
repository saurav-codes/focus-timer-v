import copy
from datetime import datetime
import json
import logging
from channels.generic.websocket import AsyncWebsocketConsumer
from django.http import HttpRequest
from django.shortcuts import get_object_or_404
from .business_logic import selectors
from .business_logic.services import AsyncTimerService
from .models import FocusSession, FocusSessionFollower
from channels.db import database_sync_to_async
import redis.asyncio as aioredis
from django.conf import settings
from django.utils import timezone

from functools import wraps

logger = logging.getLogger(__name__)


def async_session_owner_only(func):
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


def async_internal_action_only(func):
    """
    Decorator to check if the action is performed by an internal action
    it should never be called by a client so the goal of this decorator
    is to make sure that this action is never called by a client
    """

    @wraps(func)
    async def wrapper(self, *args, **kwargs):
        user = self.scope["user"]
        text_data = json.loads(args[0])
        secret_key = text_data.get("secret_key")
        if secret_key != settings.CYCLE_CHANGE_INTERNAL_SECRET_KEY:
            logger.info(
                f"{user.username} tried to perform an internal action on session '{self.session_id}' but was not authorized"
            )
            await self.send(text_data=json.dumps({"error": "this action is restricted to the system."}))

        return await func(self, *args, **kwargs)

    return wrapper


class FocusSessionConsumer(AsyncWebsocketConsumer):
    async def connect(self):
        self.redis_client = await aioredis.from_url(f"redis://{settings.REDIS_HOST}:{settings.REDIS_PORT}")
        self.user = self.scope["user"]
        self.username = self.scope["url_route"]["kwargs"]["username"]
        self.session_id = self.scope["url_route"]["kwargs"]["session_id"]
        self.session_group_name = f"focus_session_{self.session_id}"
        self.request = self._generate_request_metadata()
        self.session = await database_sync_to_async(get_object_or_404)(
            FocusSession,
            session_id=self.session_id,
        )
        self.timer_service = AsyncTimerService(session=self.session, user=self.user)

        await self.channel_layer.group_add(self.session_group_name, self.channel_name)  # type: ignore
        await self.accept()
        # even though we should be sending timer update to only connected client
        # but since we are some tab sleep issues, we are sending it to all connected clients
        await self.send_timer_update_to_all_clients()
        await self._schedule_next_cycle_change()

        # add client to connected clients list
        await self._create_session_follower()
        logger.info(f"{self.user.username} connected to session '{self.session_id}'", extra={"request": self.request})
        await self.update_session_followers_list_to_all_clients()

    def _generate_request_metadata(self):
        request = HttpRequest()
        user_agent = str(self.scope["headers"][4][1].strip())
        try:
            ip_add = self.scope["client"][0]
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
        request.user = self.user
        return request

    async def disconnect(self, close_code):
        # websocket is disconnect for whatever reasons
        # so we will save the session
        if self.user == await self.timer_service._get_session_owner():
            # only owner can save the session
            # because other are just followers
            await self.timer_service._save_last_focus_period_of_current_session()
            if self.session.timer_state == FocusSession.TIMER_RUNNING:
                # since the timer is running, we will create a new focus period
                # which will be the last focus period of the session
                # TODO: perform this action in a transaction or lock
                await self.timer_service._create_new_focus_period()
                logger.info(
                    f"Created new focus period for session '{self.session_id}' on owner disconnect",
                    extra={"request": self.request},
                )
        # remove user from followers list
        logger.info(
            f"{self.user.username} disconnected from session '{self.session_id}'", extra={"request": self.request}
        )
        await self._delete_session_follower()
        # send updated followers list to all clients
        await self.update_session_followers_list_to_all_clients()
        # remove this client from the session group so
        # that it will not receive any messages
        await self.channel_layer.group_discard(self.session_group_name, self.channel_name)  # type: ignore
        # also cancel any scheduled cycle change
        await self._cancel_scheduled_cycle_change()

    @database_sync_to_async
    def _delete_session_follower(self):
        logger.info(
            f"Removing user '{self.username}' from session '{self.session_id}' followers",
            extra={"request": self.request},
        )
        FocusSessionFollower.objects.filter(session=self.session, username=self.username).delete()

    @database_sync_to_async
    def _create_session_follower(self):
        if self.user.is_authenticated:
            FocusSessionFollower.objects.get_or_create(
                session=self.session,
                user=self.user,
                username=self.username,
                user_type="authenticated",
            )
        else:
            FocusSessionFollower.objects.get_or_create(
                session=self.session,
                username=self.username,
                user_type="guest",
            )

    async def receive(self, text_data):
        """
        Receive message from the client.
        """
        data = json.loads(text_data)
        action = data.get("action")
        if action == "toggle_timer":
            await self.toggle_timer(text_data)
        if action == "stop_timer":
            await self.stop_timer()
        if action == "sync_inactive_timer":
            logger.info(
                f"Syncing inactive timer for user '{self.user.username}' in session '{self.session_id}'",
                extra={"request": self.request},
            )
            await self.sync_inactive_timer(text_data)
        if action == "cycle_change":
            await self.change_cycle_if_needed(text_data)
        if action == "timer_update":
            await self.send_timer_update_to_all_clients()

    @async_session_owner_only
    async def toggle_timer(self, text_data):
        logger.info(
            f"Toggling timer for user '{self.user.username}' in session '{self.session_id}'",
            extra={"request": self.request},
        )
        timer_state = await self.timer_service.toggle_timer()
        if timer_state == "paused":
            await self._cancel_scheduled_cycle_change()
        elif timer_state == "resumed":
            await self._schedule_next_cycle_change()

    @async_internal_action_only
    @async_session_owner_only
    async def change_cycle_if_needed(self, text_data):
        """
        This function is called by the system to change the cycle if needed
        it is called when the timer is stopped or when the timer is paused/resumed
        usually it will be called by system on the scheduled time as we are using
        redis zset to store the scheduled time to change the cycle
        """
        logger.info(
            f"Changing cycle if needed for user '{self.user.username}' in session '{self.session_id}'",
            extra={"request": self.request},
        )
        await self.timer_service.change_cycle_if_needed()
        # now we have new cycle so we need to schedule the next cycle change
        await self._schedule_next_cycle_change()

    async def _schedule_next_cycle_change(self):
        if self.session.timer_state == FocusSession.TIMER_RUNNING:
            current_cycle = await self.timer_service._get_current_cycle()
            all_focus_period_duration = await self.timer_service._get_all_focus_period_duration_for_current_cycle(
                current_cycle
            )
            remaining_time = current_cycle.duration.seconds - all_focus_period_duration.seconds
            if remaining_time < 0:
                remaining_time = 0
                logger.info(
                    f"{self.user.username} cycle is already completed and we are above the scheduled time, \
                        so we scheduling the current cycle to change right now",
                    extra={"request": self.request},
                )
            next_change_time = timezone.now() + timezone.timedelta(seconds=remaining_time)
            # first we need to check if there is already a scheduled change for this session
            await self.redis_client.zadd(
                "scheduled_cycle_changes", {str(self.session.session_id): next_change_time.timestamp()}
            )
            logger.info(
                f"Scheduled next cycle change for user '{self.user.username}' in session '{self.session_id}' at {next_change_time}",
                extra={"request": self.request},
            )
        else:
            logger.info(
                f"Not scheduling next cycle change for user '{self.user.username}' in session '{self.session_id}' because the timer is not running",
                extra={"request": self.request},
            )

    async def _cancel_scheduled_cycle_change(self):
        await self.redis_client.zrem("scheduled_cycle_changes", str(self.session.session_id))

    @async_session_owner_only
    async def stop_timer(self):
        logger.info(
            f"Stopping timer for user '{self.user.username}' in session '{self.session_id}'",
            extra={"request": self.request},
        )
        await self.timer_service.stop_timer()
        await self._cancel_scheduled_cycle_change()

    async def send_timer_update_to_all_clients(self):
        timer_display_data = await self.timer_service.get_timer_display_data()
        await self.channel_layer.group_send(  # type: ignore
            self.session_group_name,
            {
                "type": "timer_update",
                "timer_display_data": timer_display_data,
            },
        )
        logger.info(f"Sent timer update to all clients in session '{self.session_id}'", extra={"request": self.request})

    async def timer_update(self, data):
        await self.send(text_data=json.dumps(data))

    @database_sync_to_async
    def _get_session_will_finish_at_data(self):
        will_finish_at = selectors.get_session_will_finish_at(request_user=self.user, session=self.session)
        return will_finish_at

    async def update_session_will_finish_at_to_all_clients(self):
        await self.channel_layer.group_send(  # type: ignore
            self.session_group_name,
            {
                "type": "will_finish_at_update",
            },
        )

    async def will_finish_at_update(self, data):
        will_finish_at_timestamp = await self._get_session_will_finish_at_data()
        await self.send(
            text_data=json.dumps(
                {"will_finish_at_timestamp": will_finish_at_timestamp, "type": "will_finish_at_update"}
            )
        )

    async def update_session_followers_list_to_all_clients(self):
        session_followers_list = await self._get_session_followers_list()
        await self.channel_layer.group_send(  # type: ignore
            self.session_group_name,
            {
                "type": "followers_update",
                "followers": session_followers_list,
            },
        )

    @database_sync_to_async
    def _get_session_followers_list(self):
        session_followers = FocusSessionFollower.objects.filter(session=self.session)
        session_followers_list = {}
        for follower in session_followers:
            session_followers_list[follower.username] = {
                "user_type": follower.user_type,
                "joined_at": follower.joined_at.isoformat(),
            }
        return session_followers_list

    async def followers_update(self, data):
        followers_data = copy.deepcopy(data.get("followers", []))
        if self.username in followers_data.keys():
            followers_data[self.username]["coloured_username"] = True
        response_data = {
            "type": "followers_update",
            "followers": followers_data,
        }
        await self.send(text_data=json.dumps(response_data))

    async def sync_inactive_timer(self, text_data):
        """
        Sometime OS or Browser pauses the timer from
        client side and then clientside have not idea
        about the server time. so we update that time here
        """
        logger.info(
            f"Syncing inactive timer for session '{self.session_id}' at {datetime.now()}",
            extra={"request": self.request},
        )
        await self.send_timer_update_to_all_clients()
        await self.update_session_will_finish_at_to_all_clients()
        await self.update_session_followers_list_to_all_clients()

    async def cycle_change(self, event):
        """
        Handle the cycle_change event sent by the Redis scheduler.
        """
        logger.info(f"Received cycle_change event for session '{self.session_id}'")
        await self.change_cycle_if_needed(
            json.dumps({"action": "cycle_change", "secret_key": settings.CYCLE_CHANGE_INTERNAL_SECRET_KEY})
        )
