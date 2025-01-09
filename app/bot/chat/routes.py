from fastapi import APIRouter, HTTPException, Body, Request
from app.bot.dialogue_manager.models import ChatModel

router = APIRouter(prefix="/v1", tags=["bots"])

@router.post("/chat")
async def chat(request: Request, body: dict):
    """
    Endpoint to converse with the chatbot.
    Delegates the request processing to DialogueManager.

    :return: JSON response with the chatbot's reply and context.
    """
    try:
        # Access the dialogue manager from the fast api application state.
        chat_request = ChatModel.from_json(body)
        chat_response = request.app.state.dialogue_manager.process(chat_request)
        return chat_response.to_json()
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error processing request: {e}")
