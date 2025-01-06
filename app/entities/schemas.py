from pydantic import BaseModel, Field
from typing import List, Optional, Dict, Any
from datetime import datetime, UTC
from bson import ObjectId

def empty_list() -> List[Any]:
    return []

def utc_now() -> datetime:
    """Get current UTC datetime with timezone information"""
    return datetime.now(UTC)

class EntityValue(BaseModel):
    """Schema for entity value"""
    value: str
    synonyms: List[str] = Field(default_factory=lambda: empty_list)

class EntityBase(BaseModel):
    """Base schema for entity"""
    name: str
    entityValues: List[EntityValue] = Field(default_factory=lambda: empty_list)
    created_at: datetime = Field(default_factory=utc_now)
    updated_at: datetime = Field(default_factory=utc_now)

    class Config:
        allow_population_by_field_name = True
        json_encoders = {
            datetime: lambda dt: dt.isoformat()
        }

class EntityCreate(EntityBase):
    """Schema for creating an entity"""
    pass

class EntityUpdate(EntityBase):
    """Schema for updating an entity"""
    pass

class EntityInDB(EntityBase):
    """Schema for entity in database"""
    id: ObjectId = Field(alias="_id")

    class Config:
        allow_population_by_field_name = True
        arbitrary_types_allowed=True
        json_encoders = {
            ObjectId: str,
            datetime: lambda dt: dt.isoformat()
        }

class EntityResponse(BaseModel):
    """Schema for entity response"""
    status: str = "success"
    result: bool = True
    data: Optional[Dict[str, Any]] = None
    message: Optional[str] = None

class EntityListResponse(BaseModel):
    """Schema for entity list response"""
    name: str
    id: str 