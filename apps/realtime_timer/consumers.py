import copy
from datetime import datetime
import json
from channels.generic.websocket import AsyncWebsocketConsumer
from django.shortcuts import get_object_or_404
from .business_logic import selectors
from .business_logic.services import AsyncTimerService
from .models import FocusSession, FocusSessionFollower
from channels.db import database_sync_to_async

from functools import wraps


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
            # this usually happens when the user is not the session owner
            # and to tackle sleeping tabs issue, we will manually
            # send the timer update to all clients when this happens
            print(
                "seems like the user is not the session owner & incase\
                  this maybe a sleeping tab issue, we are sending latest updates of \
                  timer and followers and other data to all clients"
            )
            await self.sync_inactive_timer()
            return
        return await func(self, *args, **kwargs)

    return wrapper


class FocusSessionConsumer(AsyncWebsocketConsumer):
    async def connect(self):
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
        await self.send_timer_update_to_all_clients()

        # add client to connected clients list
        await self._create_session_follower()
        print(f"connected clients: {self.username}")
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
                await self.timer_service._create_new_focus_period()
                print("created new focus period when user disconnected")
        # remove user from followers list
        print(f"deleting user {self.username} from followers list")
        await self._delete_session_follower()
        # send updated followers list to all clients
        await self.update_session_followers_list_to_all_clients()
        await self.channel_layer.group_discard(self.session_group_name, self.channel_name)  # type: ignore

    @database_sync_to_async
    def _delete_session_follower(self):
        print(f"deleting user {self.username} from followers list")
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
            await self.toggle_timer()
        if action == "transition_to_next_cycle":
            print(f"switching to next cycle for user {self.user.username}")
            await self.transition_to_next_cycle()
        if action == "stop_timer":
            await self.stop_timer()
        if action == "followers_update":
            print("updating session followers list")
            await self.update_session_followers_list_to_all_clients()
        if action == "sync_inactive_timer":
            print(f"syncing inactive timer for {self.user.username}")
            await self.sync_inactive_timer()

    @async_session_owner_only
    async def toggle_timer(self):
        await self.timer_service.toggle_timer()
        await self.send_timer_update_to_all_clients()
        await self.update_session_will_finish_at_to_all_clients()

    @async_session_owner_only
    async def stop_timer(self):
        await self.timer_service.stop_timer()
        await self.send_timer_update_to_all_clients()

    @async_session_owner_only
    async def transition_to_next_cycle(self):
        await self.timer_service.transition_to_next_cycle()
        await self.send_timer_update_to_all_clients()
        await self.update_session_will_finish_at_to_all_clients()

    async def send_timer_update_to_all_clients(self):
        timer_display_data = await self.timer_service.get_timer_display_data()
        await self.channel_layer.group_send(  # type: ignore
            self.session_group_name,
            {
                "type": "timer_update",
                "timer_display_data": timer_display_data,
            },
        )

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
        # we don't need to calculate followers list for each client
        # we can just send the followers list to all clients
        session_followers_list = await self._get_session_followers_list()
        # we need to keep only the active clients
        # import ipdb; ipdb.set_trace()
        # Get all active clients in the session group
        # active_clients = await self.channel_layer.group_channels(self.session_group_name)

        # Extract usernames from active clients
        # active_usernames = set()
        # for channel in active_clients:
        #     channel_user = await self.channel_layer.get_channel_user(channel)
        #     if channel_user:
        #         active_usernames.add(channel_user.username)

        # Filter session_followers_list to keep only active clients
        # session_followers_list = {
        #     username: data
        #     for username, data in session_followers_list.items()
        #     if username in active_usernames
        # }
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

    async def sync_inactive_timer(self):
        """
        Sometime OS or Browser pauses the timer from
        client side and then clientside have not idea
        about the server time. so we update that time here
        """
        print("syncing inactive timer", datetime.now())
        await self.send_timer_update_to_all_clients()
        await self.update_session_will_finish_at_to_all_clients()
        await self.update_session_followers_list_to_all_clients()
