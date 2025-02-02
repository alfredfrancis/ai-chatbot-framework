from fastapi import APIRouter, Depends, HTTPException
from app.bot.dialogue_manager.models import UserMessage
from app.dependencies import get_dialogue_manager
from app.bot.dialogue_manager.dialogue_manager import (
    DialogueManager,
    DialogueManagerException,
)

router = APIRouter(prefix="/rest", tags=["rest"])


@router.post("/webbook")
async def webbook(
    body: dict, dialogue_manager: DialogueManager = Depends(get_dialogue_manager)
):
    """
    Endpoint to converse with the chatbot.
    Delegates the request processing to DialogueManager.

    :return: JSON response with the chatbot's reply and context.
    """

    user_message = UserMessage(
        thread_id=body["thread_id"], text=body["text"], context=body["context"]
    )
    try:
        new_state = await dialogue_manager.process(user_message)
    except DialogueManagerException as e:
        raise HTTPException(status_code=400, message=str(e))
    return new_state.bot_message
