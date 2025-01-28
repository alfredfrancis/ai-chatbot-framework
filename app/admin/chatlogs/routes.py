from fastapi import APIRouter
from typing import Optional
from datetime import datetime
import app.admin.chatlogs.store as store

router = APIRouter(prefix="/chatlogs", tags=["chatlogs"])


@router.get("/")
async def list_chatlogs(
    page: int = 1,
    limit: int = 10,
    start_date: Optional[datetime] = None,
    end_date: Optional[datetime] = None,
):
    """Get paginated chat conversation history with optional date filtering"""
    return await store.list_chatlogs(page, limit, start_date, end_date)


@router.get("/{thread_id}")
async def get_chat_thread(thread_id: str):
    """Get complete conversation history for a specific thread"""
    conversation = await store.get_chat_thread(thread_id)
    if not conversation:
        return {"error": "Conversation not found"}

    return conversation
