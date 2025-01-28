from pydantic import BaseModel
from typing import Dict, List, Optional
from datetime import datetime


class ChatMessage(BaseModel):
    text: str
    context: Optional[Dict] = {}


class ChatThreadInfo(BaseModel):
    thread_id: str
    date: datetime


class BotNessage(BaseModel):
    text: str


class ChatLog(BaseModel):
    user_message: ChatMessage
    bot_message: List[BotNessage]
    date: datetime
    context: Optional[Dict] = {}


class ChatLogResponse(BaseModel):
    total: int
    page: int
    limit: int
    conversations: List[ChatThreadInfo]
