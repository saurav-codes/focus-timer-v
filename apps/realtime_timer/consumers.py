import json
from channels.generic.websocket import AsyncWebsocketConsumer
from django.shortcuts import get_object_or_404
from .business_logic.services import AsyncTimerService
from .models import FocusSession
from channels.db import database_sync_to_async

from functools import wraps


def async_session_owner_only(func):
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
            return
        return await func(self, *args, **kwargs)

    return wrapper


class FocusSessionConsumer(AsyncWebsocketConsumer):
    async def connect(self):
        self.session_id = self.scope["url_route"]["kwargs"]["session_id"]
        self.session_group_name = f"focus_session_{self.session_id}"
        self.session = await database_sync_to_async(get_object_or_404)(
            FocusSession,
            session_id=self.session_id,
        )
        self.timer_service = AsyncTimerService(session=self.session)

        await self.channel_layer.group_add(self.session_group_name, self.channel_name)
        await self.accept()
        await self.send_timer_update_to_all_clients()
        await self.update_session_followers_list_to_all_clients()

    async def disconnect(self, close_code):
        # websocket is disconnect for whatever reasons
        # so we will save the session
        await self.timer_service._save_last_focus_period_of_current_session()
        if self.session.timer_state == FocusSession.TIMER_RUNNING:
            # since the timer is running, we will create a new focus period
            # which will be the last focus period of the session
            await self.timer_service._create_new_focus_period()
        await self.channel_layer.group_discard(self.session_group_name, self.channel_name)

    async def receive(self, text_data):
        """
        Receive message from the client.
        """
        data = json.loads(text_data)
        action = data.get("action")
        print(action)
        if action == "toggle_timer":
            await self.toggle_timer()
        if action == "transition_to_next_cycle":
            print("switching to next cycle")
            await self.timer_service.transition_to_next_cycle()
            await self.send_timer_update_to_all_clients()
        if action == "stop_timer":
            await self.stop_timer()
        if action == "followers_update":
            print("updating session followers list")
            await self.update_session_followers_list_to_all_clients()

    @async_session_owner_only
    async def toggle_timer(self):
        await self.timer_service.toggle_timer()
        await self.send_timer_update_to_all_clients()

    @async_session_owner_only
    async def stop_timer(self):
        await self.timer_service.stop_timer()
        await self.send_timer_update_to_all_clients()

    async def send_timer_update_to_all_clients(self):
        timer_display_data = await self.timer_service.get_timer_display_data()
        await self.channel_layer.group_send(
            self.session_group_name,
            {
                "type": "timer_update",
                "timer_display_data": timer_display_data,
            },
        )

    async def timer_update(self, data):
        await self.send(text_data=json.dumps(data))

    @database_sync_to_async
    def _get_followers_data(self):
        followers = self.session.followers.all()
        followers_data = [
            {"username": follower.follower.username, "joined_at": follower.joined_at.isoformat()}
            for follower in followers
        ]
        return followers_data

    async def update_session_followers_list_to_all_clients(self):
        followers_data = await self._get_followers_data()
        await self.channel_layer.group_send(  # type: ignore
            self.session_group_name,
            {
                "type": "followers_update",
                "followers": followers_data,
            },
        )

    async def followers_update(self, data):
        await self.send(text_data=json.dumps(data))
