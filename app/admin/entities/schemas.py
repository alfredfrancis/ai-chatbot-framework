from pydantic import BaseModel, Field
from typing import List
from app.database import ObjectIdField

class EntityValue(BaseModel):
    """Schema for entity value"""
    value: str
    synonyms: List[str] = []

class Entity(BaseModel):
    """Schema for entity"""
    id: ObjectIdField = Field(validation_alias="_id", default=None)
    name: str
    entity_values: List[EntityValue] = []

    class Config:
        arbitrary_types_allowed=True