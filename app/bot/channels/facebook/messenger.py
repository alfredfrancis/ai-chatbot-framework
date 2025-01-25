import hashlib
import hmac
import logging
from typing import Dict, Any, List
import aiohttp
from fastapi import HTTPException

from app.bot.dialogue_manager.models import UserMessage
from app.bot.dialogue_manager.dialogue_manager import DialogueManager

logger = logging.getLogger(__name__)

FACEBOOK_API_URL = "https://graph.facebook.com/v18.0/me/messages"


class FacebookSender:
    """Handles sending messages to Facebook Messenger."""

    def __init__(self, access_token: str):
        self.access_token = access_token

    async def send_message(self, recipient_id: str, message: Dict[str, Any]):
        """Send a message to Facebook Messenger."""
        payload = {"recipient": {"id": recipient_id}, "message": message}

        params = {"access_token": self.access_token}

        async with aiohttp.ClientSession() as session:
            async with session.post(
                FACEBOOK_API_URL, json=payload, params=params
            ) as response:
                if response.status != 200:
                    error_data = await response.json()
                    logger.error(f"Error sending message to Facebook: {error_data}")
                    raise HTTPException(
                        status_code=500, detail="Failed to send message to Facebook"
                    )
                return await response.json()

    def format_bot_response(self, bot_message: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Format bot response into Facebook message format."""
        messages = [bot_message]
        return messages


class FacebookReceiver:
    """Handles receiving and processing messages from Facebook Messenger."""

    def __init__(self, config: Dict[str, Any], dialogue_manager: DialogueManager):
        self.config = config
        self.dialogue_manager = dialogue_manager
        self.sender = FacebookSender(config["page_access_token"])

    def validate_hub_signature(
        self, request_payload: bytes, hub_signature_header: str
    ) -> bool:
        """Validate the request signature from Facebook."""
        try:
            hash_method, hub_signature = hub_signature_header.split("=")
            digest_module = getattr(hashlib, hash_method)
            hmac_object = hmac.new(
                bytearray(self.config["secret"], "utf8"), request_payload, digest_module
            )
            generated_hash = hmac_object.hexdigest()
            return hub_signature == generated_hash
        except Exception:
            return False

    async def handle_message(
        self, sender_id: str, message_text: str, context: Dict[str, Any]
    ) -> None:
        """Process a message through the dialogue manager and send response."""
        user_message = UserMessage(
            thread_id=sender_id, text=message_text, context=context or {}
        )
        new_state = await self.dialogue_manager.process(user_message)

        # Format and send response back to Facebook
        for message in new_state.bot_message:
            formatted_messages = self.sender.format_bot_response(message)
            for formatted_message in formatted_messages:
                await self.sender.send_message(sender_id, formatted_message)

    async def process_webhook_event(self, data: List[Dict]) -> None:
        """Process a single webhook event."""
        # Process each entry in the webhook payload
        for entry in data.get("entry", []):
            page_id = entry.get("id")
            for messaging_event in entry.get("messaging", []):
                await self.process_messaging_event(messaging_event, page_id)

    async def process_messaging_event(
        self, event: Dict[str, Any], page_id: str
    ) -> None:
        """Process a messaging event from Facebook."""
        sender_id = event.get("sender", {}).get("id")
        if not sender_id:
            return

        if event.get("message") and "text" in event["message"]:
            # Handle text message
            await self.handle_message(
                sender_id,
                event["message"]["text"],
                {
                    "channel": "facebook",
                    "page_id": page_id,
                    "timestamp": event.get("timestamp"),
                },
            )
        elif event.get("postback"):
            print("postback")
            # Handle postback
            await self.handle_message(
                sender_id,
                event["postback"]["payload"],
                {
                    "channel": "facebook",
                    "page_id": page_id,
                    "timestamp": event.get("timestamp"),
                    "is_postback": True,
                },
            )
