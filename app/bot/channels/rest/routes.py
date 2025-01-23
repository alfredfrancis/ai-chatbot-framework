from fastapi import APIRouter, Depends
from app.bot.dialogue_manager.models import UserMessage
from app.dependencies import get_dialogue_manager
from app.bot.dialogue_manager.dialogue_manager import DialogueManager

router = APIRouter(prefix="/v1", tags=["bots"])


@router.post("/chat")
async def chat(
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
    new_state = await dialogue_manager.process(user_message)
    return new_state.bot_message
