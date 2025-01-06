from fastapi import APIRouter, HTTPException
from fastapi.responses import JSONResponse
from app.chat.schemas import ChatRequest, ChatResponse, ErrorResponse
from app.dialogue_manager.dialogue_manager import DialogueManager
from app.main import spacy_tokenizer
from datetime import datetime

router = APIRouter()

# Initialize DialogueManager
dialogue_manager = DialogueManager()

@router.on_event("startup")
async def initialize_dialogue_manager():
    """Initialize the dialogue manager on startup"""
    try:
        await dialogue_manager.update_model()
    except Exception as e:
        print(f"Error initializing dialogue manager: {str(e)}")

@router.post("/v1")
async def chat_endpoint(request: ChatRequest):
    """
    Endpoint to converse with the chatbot.
    Delegates the request processing to DialogueManager.
    """
    try:
        # Process the chat request
        response = await dialogue_manager.process(request.dict())
        
        # Add timestamp if not present
        if not response.get("date"):
            response["date"] = datetime.utcnow().isoformat()
        
        return JSONResponse(content=response)
    except ValueError as e:
        return JSONResponse(
            status_code=400,
            content={"error": str(e)}
        )
    except Exception as e:
        return JSONResponse(
            status_code=500,
            content={"error": f"Error processing chat request: {str(e)}"}
        ) 