from fastapi import APIRouter
from app.admin.intents import store
from app.admin.intents.schemas import Intent

router = APIRouter(prefix="/intents", tags=["intents"])


@router.post("/")
async def create_intent(intent: Intent):
    """Create a new intent"""
    intent_dict = intent.model_dump(exclude={"id"})
    intent = await store.add_intent(intent_dict)
    return intent


@router.get("/")
async def read_intents():
    """Get all intents"""
    return await store.list_intents()


@router.get("/{intent_id}")
async def read_intent(intent_id: str):
    """Get a specific intent by ID"""
    intent = await store.get_intent(intent_id)
    return intent


@router.put("/{intent_id}")
async def update_intent(intent_id: str, intent: Intent):
    """Update an intent"""
    intent_dict = intent.model_dump(exclude={"id"})
    await store.edit_intent(intent_id, intent_dict)
    return {"status": "success"}


@router.delete("/{intent_id}")
async def delete_intent(intent_id: str):
    """Delete an intent"""
    await store.delete_intent(intent_id)
    return {"status": "success"}
