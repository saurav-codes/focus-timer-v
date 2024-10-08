import asyncio
import redis.asyncio as redis
from django.conf import settings
from channels.layers import get_channel_layer
import logging
import time
from django.core.management.base import BaseCommand
from apps.realtime_timer.business_logic import selectors
from apps.realtime_timer.business_logic.services import AsyncTimerService
from apps.realtime_timer.models import FocusSession
from channels.db import database_sync_to_async
from apps.realtime_timer.business_logic.services import trigger_sync_timer_for_all_connected_clients

logger = logging.getLogger(__name__)


class RedisScheduler:
    def __init__(self):
        self.redis = redis.Redis.from_url(f"redis://{settings.REDIS_HOST}:{settings.REDIS_PORT}")
        self.channel_layer = get_channel_layer()

    async def run(self):
        while True:
            try:
                now = time.time()
                due_changes = await self.redis.zrangebyscore("scheduled_cycle_changes", 0, now, start=0, num=100)
                if due_changes:
                    for session_id in due_changes:
                        logger.info("--------------------------------------------")
                        await self.process_change(session_id)
                        logger.info("--------------------------------------------")
                    # TODO: remove this wait if possible
                    await asyncio.sleep(0.1)
                else:
                    spinner = "⠋⠙⠹⠸⠼⠴⠦⠧⠇⠏"
                    for _ in range(10):
                        print(f"\rWaiting for changes {spinner[_ % len(spinner)]}", end="", flush=True)
                        await asyncio.sleep(0.1)
                    print("\r" + " " * 30 + "\r", end="", flush=True)
                    await asyncio.sleep(1)
            except redis.RedisError as e:
                logger.error(f"Redis error: {e}")
                await asyncio.sleep(5)
            except Exception as e:
                logger.error(f"Unexpected error: {e}")
                await asyncio.sleep(5)

    async def process_change(self, session_id):
        try:
            session_id = session_id.decode()
            session = await selectors.get_session_by_id_async(session_id)
            session_owner = await selectors.get_session_owner_async(session)
            if not session:
                logger.error(f"Session {session_id} not found, skipping processing")
                await self.redis.zrem("scheduled_cycle_changes", session_id)
                return
            timer_service = AsyncTimerService(session_id, session_owner, session_owner.username)
            if session.timer_state == FocusSession.TIMER_RUNNING:
                logger.info(f"calling timer_service.change_cycle_if_needed for session {session_id}")
                await timer_service.change_cycle_if_needed(session)
                # logger.info(f"calling trigger_sync_timer_for_all_connected_clients for session {session_id}")
                # await trigger_sync_timer_for_all_connected_clients(session_id)
                logger.info(f"calling timer_service.schedule_next_cycle_change for session {session_id}")
                await self.redis.zrem("scheduled_cycle_changes", session_id)
                await timer_service.schedule_next_cycle_change(self.redis)
                logger.info(f"cycle change completed for session {session_id}")
            else:
                logger.info(f"session {session_id} is not running, skipping cycle change")
                await self.redis.zrem("scheduled_cycle_changes", session_id)
        except Exception as e:
            await self.redis.zrem("scheduled_cycle_changes", session_id)
            logger.error(f"Error processing change for session {session_id}: {e}")
            logger.exception("Full traceback:")


class Command(BaseCommand):
    help = "Runs the Redis scheduler for focus session cycle changes"

    def handle(self, *args, **options):
        scheduler = RedisScheduler()
        asyncio.run(scheduler.run())
