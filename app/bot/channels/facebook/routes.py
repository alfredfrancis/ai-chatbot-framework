from typing import Dict, Any
import logging
from fastapi import APIRouter, Request, HTTPException, Depends, BackgroundTasks
from app.admin.integrations.store import get_integration
from app.dependencies import get_dialogue_manager
from app.bot.dialogue_manager.dialogue_manager import DialogueManager
from .messenger import FacebookReceiver

router = APIRouter(prefix="/facebook", tags=["facebook"])
logger = logging.getLogger(__name__)


async def get_facebook_config():
    """Get Facebook integration configuration from store."""
    integration = await get_integration("facebook")
    if not integration or not integration.status:
        raise HTTPException(
            status_code=404, detail="Facebook integration not configured or disabled"
        )
    return integration.settings


@router.get("/webhook")
async def verify_webhook(
    request: Request, config: Dict[str, Any] = Depends(get_facebook_config)
):
    """Handle Facebook webhook verification."""
    hub_mode = request.query_params.get("hub.mode")
    token = request.query_params.get("hub.verify_token")
    challenge = request.query_params.get("hub.challenge")

    if hub_mode and token:
        if hub_mode == "subscribe" and token == config["verify"]:
            return int(challenge)
        raise HTTPException(status_code=403, detail="Invalid verification token")

    raise HTTPException(status_code=400, detail="Invalid request parameters")


@router.post("/webhook")
async def webhook(
    background_tasks: BackgroundTasks,
    request: Request,
    config: Dict[str, Any] = Depends(get_facebook_config),
    dialogue_manager: DialogueManager = Depends(get_dialogue_manager),
):
    """Handle incoming Facebook webhook events."""
    body = await request.body()
    signature = request.headers.get("X-Hub-Signature", "")

    facebook = FacebookReceiver(config, dialogue_manager)

    if not facebook.validate_hub_signature(body, signature):
        raise HTTPException(status_code=403, detail="Invalid request signature")

    try:
        data = await request.json()
        background_tasks.add_task(facebook.process_webhook_event, data)

        return {"success": True}
    except Exception as e:
        logger.error(f"Error processing webhook: {str(e)}")
        raise HTTPException(status_code=500, detail="Error processing webhook")
