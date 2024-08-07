import json
from channels.generic.websocket import AsyncWebsocketConsumer
from channels.db import database_sync_to_async
from .business_logic import services, selectors


class FocusSessionConsumer(AsyncWebsocketConsumer):
    async def connect(self):
        self.session_id = self.scope["url_route"]["kwargs"]["session_id"]
        self.session_group_name = f"focus_session_{self.session_id}"

        # Join room group
        await self.channel_layer.group_add(self.session_group_name, self.channel_name)

        await self.accept()

    async def disconnect(self, close_code):
        # Leave room group
        await self.channel_layer.group_discard(self.session_group_name, self.channel_name)

    async def receive(self, text_data):
        data = json.loads(text_data)
        action = data["action"]

        if action == "start_timer":
            await self.start_timer()
        elif action == "pause_timer":
            await self.pause_timer()
        elif action == "stop_timer":
            await self.stop_timer()
        elif action == "create_task":
            await self.create_task(data["description"])
        elif action == "toggle_task":
            await self.toggle_task(data["task_id"])

    async def session_update(self, event):
        # Send message to WebSocket
        await self.send(text_data=json.dumps(event))

    @database_sync_to_async
    def start_timer(self):
        session = selectors.get_focus_session_by_id(session_id=self.session_id)
        services.start_timer(session=session)
        return selectors.get_elapsed_time(session=session)

    @database_sync_to_async
    def pause_timer(self):
        session = selectors.get_focus_session_by_id(session_id=self.session_id)
        services.pause_timer(session=session)
        return selectors.get_elapsed_time(session=session)

    @database_sync_to_async
    def stop_timer(self):
        session = selectors.get_focus_session_by_id(session_id=self.session_id)
        services.stop_timer(session=session)
        return selectors.get_elapsed_time(session=session)

    @database_sync_to_async
    def create_task(self, description):
        session = selectors.get_focus_session_by_id(session_id=self.session_id)
        task = services.create_task(session=session, description=description)
        return {"id": task.pk, "description": task.description, "is_completed": task.is_completed}

    @database_sync_to_async
    def toggle_task(self, task_id):
        task = selectors.get_task_by_id(task_id=task_id)
        services.toggle_task(task=task)
        return {"id": task.pk, "description": task.description, "is_completed": task.is_completed}
