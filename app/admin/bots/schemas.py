from pydantic import BaseModel, Field
from typing import Dict, Any
from app.database import ObjectIdField

class Bot(BaseModel):
    """Base schema for bot"""
    id: ObjectIdField = Field(validation_alias="_id", default=None)
    name: str
    config: Dict[str, Any] = {}

    class Config:
        arbitrary_types_allowed=True
