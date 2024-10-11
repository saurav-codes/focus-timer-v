import copy
from datetime import datetime
import json
import logging
from channels.generic.websocket import AsyncWebsocketConsumer
from .business_logic import selectors
from .business_logic.services import AsyncTimerService
from .utils import generate_request_metadata
from .models import FocusSession
import redis.asyncio as aioredis
from django.conf import settings

from .utils import check_session_owner_async

logger = logging.getLogger(__name__)


class FocusSessionConsumer(AsyncWebsocketConsumer):
    async def connect(self, **kwargs):
        self.redis_client = await aioredis.from_url(f"redis://{settings.REDIS_HOST}:{settings.REDIS_PORT}")
        self.user = self.scope["user"]
        self.session_id = self.scope["url_route"]["kwargs"]["session_id"]
        self.username = self.scope["url_route"]["kwargs"]["username"]
        self.session_group_name = f"focus_session_{self.session_id}"
        self.request = generate_request_metadata(self.scope, self.user)
        self.timer_service = AsyncTimerService(session_id=self.session_id, user=self.user, username=self.username)

        await self.channel_layer.group_add(self.session_group_name, self.channel_name)  # type: ignore
        await self.accept()
        # even though we should be sending timer update to only connected client
        # but since we are some tab sleep issues, we are sending it to all connected clients
        session = await selectors.get_session_by_id_async(self.session_id)
        await self.send_timer_update_to_all_clients()
        await self.timer_service.schedule_only_first_cycle_change(redis_client=self.redis_client)

        # add client to connected clients list
        await self.timer_service.create_session_follower(session)
        logger.info(f"{self.user.username} connected to session '{self.session_id}'", extra={"request": self.request})
        await self.update_session_followers_list_to_all_clients()

        # Send OneSignal tag for this session
        await self.send(text_data=json.dumps({"type": "onesignal_tag", "session_id": self.session_id}))

    async def disconnect(self, close_code):
        # websocket is disconnect for whatever reasons
        # so we will save the session
        session = await selectors.get_session_by_id_async(self.session_id)
        session_owner = await selectors.get_session_owner_async(session)
        if self.user == session_owner:
            # only owner can save the session
            # because other are just followers
            await self.timer_service.save_last_focus_period(session)
            if session.timer_state == FocusSession.TIMER_RUNNING:
                # since the timer is running, we will create a new focus period
                # which will be the last focus period of the session
                # TODO: perform this action in a transaction or lock
                await self.timer_service.create_new_focus_period(session, session.current_cycle)
                logger.info(
                    f"Created new focus period for session '{self.session_id}' on owner disconnect",
                    extra={"request": self.request},
                )
        # remove user from followers list
        logger.info(
            f"{self.user.username} disconnected from session '{self.session_id}'", extra={"request": self.request}
        )
        await self.timer_service.delete_session_follower()
        # send updated followers list to all clients
        await self.update_session_followers_list_to_all_clients()
        # remove this client from the session group so
        # that it will not receive any messages
        await self.channel_layer.group_discard(self.session_group_name, self.channel_name)  # type: ignore
        # also cancel any scheduled cycle change
        await self.timer_service.cancel_scheduled_cycle_change_if_timer_stopped(self.redis_client, self.session_id)

    async def receive(self, text_data):
        """
        Receive message from the client.
        """
        data = json.loads(text_data)
        action = data.get("action")
        if action:
            if action == "toggle_timer":
                await self.toggle_timer()
            if action == "stop_timer":
                await self.stop_timer()
            if action == "timer_update":
                await self.send_timer_update_to_all_clients()
            if action == "sync_timer":
                logger.info(
                    f"Syncing timer for user '{self.user.username}' in session '{self.session_id}'",
                    extra={"request": self.request},
                )
                await self.sync_timer(text_data)

    @check_session_owner_async
    async def toggle_timer(self):
        logger.info(
            f"Toggling timer for user '{self.user.username}' in session '{self.session_id}'",
            extra={"request": self.request},
        )
        timer_state = await self.timer_service.toggle_timer()
        if timer_state == "paused":
            await self.timer_service.cancel_scheduled_cycle_change_if_timer_stopped(self.redis_client, self.session_id)
        elif timer_state == "resumed":
            await self.timer_service.schedule_next_cycle_change(redis_client=self.redis_client)

    # @check_session_owner_async
    # async def change_cycle_if_needed(self, session):
    #     """
    #     This function is called by the system to change the cycle if needed
    #     it is called when the timer is stopped or when the timer is paused/resumed
    #     usually it will be called by system on the scheduled time as we are using
    #     redis zset to store the scheduled time to change the cycle
    #     """
    #     logger.info(
    #         f"Changing cycle if needed for user '{self.user.username}' in session '{self.session_id}'",
    #         extra={"request": self.request},
    #     )
    #     cycle_changed = await self.timer_service.change_cycle_if_needed(session=session)
    #     if cycle_changed:
    #         # Send notification when cycle changes
    #         cycle_type = session.current_cycle.cycle_type.lower()
    #         message = f"Time's up! Your {cycle_type} session has ended."
    #         logger.info("cycle is completed. so sending notification")
    #         await send_onesignal_notification(self.session_id, message)
    #     else:
    #         logger.info("cycle is not completed. so not sending notification")

    #     # now we have new cycle so we need to schedule the next cycle change
    #     await self.timer_service.schedule_next_cycle_change(redis_client=self.redis_client)

    @check_session_owner_async
    async def stop_timer(self):
        logger.info(
            f"Stopping timer for user '{self.user.username}' in session '{self.session_id}'",
            extra={"request": self.request},
        )
        await self.timer_service.stop_timer()
        await self.timer_service.cancel_scheduled_cycle_change_if_timer_stopped(self.redis_client, self.session_id)

    async def send_timer_update_to_all_clients(self):
        session = await selectors.get_session_by_id_async(self.session_id)
        timer_display_data = await selectors.get_timer_display_data(session)
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

    async def update_session_will_finish_at_to_all_clients(self):
        await self.channel_layer.group_send(  # type: ignore
            self.session_group_name,
            {
                "type": "will_finish_at_update",
            },
        )

    async def will_finish_at_update(self, data):
        session = await selectors.get_session_by_id_async(self.session_id)
        will_finish_at = await selectors.get_session_will_finish_at_async(session=session)
        await self.send(text_data=json.dumps({"will_finish_at": will_finish_at, "type": "will_finish_at_update"}))

    async def update_session_followers_list_to_all_clients(self):
        session = await selectors.get_session_by_id_async(self.session_id)
        session_followers_list = await selectors.get_session_followers_list_async(session=session)
        await self.channel_layer.group_send(  # type: ignore
            self.session_group_name,
            {
                "type": "followers_update",
                "followers": session_followers_list,
            },
        )

    async def followers_update(self, data):
        followers_data = copy.deepcopy(data.get("followers", []))
        if self.username in followers_data.keys():
            followers_data[self.username]["coloured_username"] = True
        response_data = {
            "type": "followers_update",
            "followers": followers_data,
        }
        await self.send(text_data=json.dumps(response_data))

    async def sync_timer(self, text_data):
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

    # async def cycle_change(self, event):
    #     """
    #     Handle the cycle_change event sent by the Redis scheduler.
    #     """
    #     logger.info(f"Received cycle_change event for session '{self.session_id}'")
    #     session = await selectors.get_session_by_id_async(self.session_id)
    #     await self.change_cycle_if_needed(session=session)
