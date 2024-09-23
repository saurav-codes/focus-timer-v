import copy
from datetime import datetime
import json
import logging
from channels.generic.websocket import AsyncWebsocketConsumer
from django.shortcuts import get_object_or_404
from .business_logic import selectors
from .business_logic.services import AsyncTimerService
from .models import FocusSession, FocusSessionFollower
from channels.db import database_sync_to_async
import redis_lock
import redis
from django.conf import settings

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
            await self.send(text_data=json.dumps({"error": "You are not authorized to perform this action."}))

        return await func(self, *args, **kwargs)

    return wrapper


class FocusSessionConsumer(AsyncWebsocketConsumer):
    async def connect(self):
        self.redis_client = redis.Redis.from_url(f"redis://{settings.REDIS_HOST}:{settings.REDIS_PORT}")
        self.user = self.scope["user"]
        self.username = self.scope["url_route"]["kwargs"]["username"]
        self.session_id = self.scope["url_route"]["kwargs"]["session_id"]
        self.session_group_name = f"focus_session_{self.session_id}"
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

        # add client to connected clients list
        await self._create_session_follower()
        logger.info(f"User '{self.username}' connected to session '{self.session_id}'")
        await self.update_session_followers_list_to_all_clients()

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
                logger.info(f"Created new focus period for session '{self.session_id}' on owner disconnect")
        # remove user from followers list
        logger.info(f"User '{self.username}' disconnected from session '{self.session_id}'")
        await self._delete_session_follower()
        # send updated followers list to all clients
        await self.update_session_followers_list_to_all_clients()
        # remove this client from the session group so
        # that it will not receive any messages
        await self.channel_layer.group_discard(self.session_group_name, self.channel_name)  # type: ignore

    @database_sync_to_async
    def _delete_session_follower(self):
        logger.info(f"Removing user '{self.username}' from session '{self.session_id}' followers")
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
            logger.info(f"Syncing inactive timer for user '{self.user.username}' in session '{self.session_id}'")
            await self.sync_inactive_timer(text_data)
        if action == "timer_update":
            await self.send_timer_update_to_all_clients()

    @async_session_owner_only
    async def toggle_timer(self, text_data):
        logger.info(f"Toggling timer for user '{self.user.username}' in session '{self.session_id}'")
        await self.timer_service.toggle_timer()

    @async_session_owner_only
    async def stop_timer(self):
        logger.info(f"Stopping timer for user '{self.user.username}' in session '{self.session_id}'")
        await self.timer_service.stop_timer()

    async def send_timer_update_to_all_clients(self):
        timer_display_data = await self.timer_service.get_timer_display_data()
        await self.channel_layer.group_send(  # type: ignore
            self.session_group_name,
            {
                "type": "timer_update",
                "timer_display_data": timer_display_data,
            },
        )
        logger.info(f"Sent timer update to all clients in session '{self.session_id}'")

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
        logger.info(f"Syncing inactive timer for session '{self.session_id}' at {datetime.now()}")
        await self.send_timer_update_to_all_clients()
        await self.update_session_will_finish_at_to_all_clients()
        await self.update_session_followers_list_to_all_clients()
