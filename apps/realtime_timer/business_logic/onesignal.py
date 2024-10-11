import aiohttp
from django.conf import settings
import logging

logger = logging.getLogger(__name__)


async def send_onesignal_notification(session_id, message):
    headers = {"Authorization": f"Basic {settings.ONESIGNAL_REST_API_KEY}", "Content-Type": "application/json"}
    payload = {
        "app_id": settings.ONESIGNAL_APP_ID,
        "included_segments": ["Subscribed Users"],
        "contents": {"en": message},
        "headings": {"en": "Focus Timer"},
        "filters": [{"field": "tag", "key": "session_id", "relation": "=", "value": str(session_id)}],
    }

    logger.info(f"🔔 Sending notification to session {session_id} with message: {message}")
    async with aiohttp.ClientSession() as session:
        async with session.post(
            "https://onesignal.com/api/v1/notifications", json=payload, headers=headers
        ) as response:
            if response.status == 200:
                logger.info(f"Notification sent successfully to session {session_id}")
            else:
                logger.error(f"Failed to send notification to session {session_id}. Status: {response.status}")
