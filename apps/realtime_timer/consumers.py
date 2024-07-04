import json
from channels.generic.websocket import AsyncWebsocketConsumer
from channels.db import database_sync_to_async
from django.utils import timezone
import asyncio


class TimerConsumer(AsyncWebsocketConsumer):
    async def connect(self):
        self.session_id = self.scope["url_route"]["kwargs"]["session_id"]
        self.session_group_name = f"timer_{self.session_id}"

        await self.channel_layer.group_add(self.session_group_name, self.channel_name)

        await self.accept()

    async def disconnect(self, close_code):
        await self.channel_layer.group_discard(self.session_group_name, self.channel_name)

    async def receive(self, text_data):
        data = json.loads(text_data)
        action = data["action"]

        if action == "pause_resume":
            await self.pause_resume_session()
        elif action == "end_session":
            await self.end_session()

    async def pause_resume_session(self):
        session = await self.get_session()
        if session.status == "active":
            session.status = "paused"
        elif session.status == "paused":
            session.status = "active"
        await self.save_session(session)

        await self.channel_layer.group_send(
            self.session_group_name, {"type": "session_update", "status": session.status}
        )

    async def end_session(self):
        session = await self.get_session()
        session.status = "completed"
        session.end_time = timezone.now()
        await self.save_session(session)

        await self.channel_layer.group_send(self.session_group_name, {"type": "session_update", "status": "completed"})

    async def session_update(self, event):
        await self.send(text_data=json.dumps(event))

    @database_sync_to_async
    def get_session(self):
        from .models import Session  # Import here to avoid app registry issues

        return Session.objects.get(id=self.session_id)

    @database_sync_to_async
    def save_session(self, session):
        session.save()

    async def timer_tick(self):
        while True:
            session = await self.get_session()
            if session.status == "active":
                current_interval = await self.get_current_interval(session)
                if current_interval:
                    elapsed = (timezone.now() - current_interval.start_time).total_seconds()
                    remaining = max(0, current_interval.duration - elapsed)
                    await self.channel_layer.group_send(
                        self.session_group_name,
                        {"type": "session_update", "time": f"{int(remaining // 60):02d}:{int(remaining % 60):02d}"},
                    )
                else:
                    await self.end_session()
                    break
            await asyncio.sleep(1)

    @database_sync_to_async
    def get_current_interval(self, session):
        return session.intervals.filter(start_time__lte=timezone.now(), end_time__isnull=True).first()
