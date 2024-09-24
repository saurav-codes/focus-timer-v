import asyncio
import redis.asyncio as redis
from django.conf import settings
from channels.layers import get_channel_layer
import logging
import time
from django.core.management.base import BaseCommand

logger = logging.getLogger(__name__)


class RedisScheduler:
    def __init__(self):
        self.redis = redis.Redis.from_url(f"redis://{settings.REDIS_HOST}:{settings.REDIS_PORT}")
        self.channel_layer = get_channel_layer()

    async def run(self):
        while True:
            try:
                now = time.time()
                # Use ZRANGEBYSCORE with a limit to avoid large result sets
                due_changes = await self.redis.zrangebyscore(
                    "scheduled_cycle_changes", 0, now, start=0, num=100  # Process max 100 items per iteration
                )

                if due_changes:
                    for session_id in due_changes:
                        logger.info("----------------------REDIS_SCHEDULER----------------------")
                        await self.process_change(session_id)
                        logger.info("----------------------REDIS_SCHEDULER----------------------")

                    # Adaptive sleep: sleep less if there were changes
                    await asyncio.sleep(0.1)
                else:
                    # Sleep longer if no changes were found
                    # More visually appealing Unicode-based spinner
                    spinner = "⠋⠙⠹⠸⠼⠴⠦⠧⠇⠏"
                    for _ in range(10):  # Spin for about 1 second
                        print(f"\rWaiting for changes {spinner[_ % len(spinner)]}", end="", flush=True)
                        await asyncio.sleep(0.1)
                    print("\r" + " " * 30 + "\r", end="", flush=True)  # Clear the spinner
                    await asyncio.sleep(1)

            except redis.RedisError as e:
                logger.error(f"Redis error: {e}")
                await asyncio.sleep(5)  # Back off on errors
            except Exception as e:
                logger.error(f"Unexpected error: {e}")
                await asyncio.sleep(5)

    async def process_change(self, session_id):
        try:
            logger.info(f"redis_scheduler: Processing change for session {session_id}")
            await self.channel_layer.group_send(  # type: ignore
                f"focus_session_{session_id.decode()}",
                {
                    "type": "cycle_change",
                },
            )
            logger.info(f"redis_scheduler: Sent cycle_change event for session {session_id}")
            await self.redis.zrem("scheduled_cycle_changes", session_id)
            logger.info(f"redis_scheduler: Removed scheduled_cycle_changes for session queue with key {session_id}")
        except Exception as e:
            logger.error(f"Error processing change for session {session_id}: {e}")


class Command(BaseCommand):
    help = "Runs the Redis scheduler for focus session cycle changes"

    def handle(self, *args, **options):
        scheduler = RedisScheduler()
        asyncio.run(scheduler.run())
