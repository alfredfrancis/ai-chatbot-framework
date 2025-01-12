from fastapi import APIRouter, HTTPException, Body, Request, Depends
from app.bot.dialogue_manager.models import ChatModel
from app.dependencies import get_dialogue_manager

router = APIRouter(prefix="/v1", tags=["bots"])

@router.post("/chat")
async def chat(request: Request, body: dict, dialogue_manager = Depends(get_dialogue_manager)):
    """
    Endpoint to converse with the chatbot.
    Delegates the request processing to DialogueManager.

    :return: JSON response with the chatbot's reply and context.
    """

    # Access the dialogue manager from the fast api application state.
    chat_request = ChatModel.from_json(body)
    chat_response = await dialogue_manager.process(chat_request)
    return chat_response.to_json()

