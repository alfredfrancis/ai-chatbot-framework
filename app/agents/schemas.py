from pydantic import BaseModel, Field
from typing import Dict, Any, Optional, List
from datetime import datetime, UTC
from bson import ObjectId

def empty_dict() -> Dict[str, Any]:
    return {}

def empty_list() -> List[Any]:
    return []

def utc_now() -> datetime:
    """Get current UTC datetime with timezone information"""
    return datetime.now(UTC)

class BotConfig(BaseModel):
    """Bot configuration schema"""
    name: str
    description: Optional[str] = None
    config: Dict[str, Any] = Field(default_factory=lambda: empty_dict)
    created_at: datetime = Field(default_factory=utc_now)
    updated_at: datetime = Field(default_factory=utc_now)

    class Config:
        allow_population_by_field_name = True
        json_encoders = {
            datetime: lambda dt: dt.isoformat()
        }

class BotBase(BaseModel):
    """Base schema for bot"""
    name: str
    config: Dict[str, Any] = Field(default_factory=lambda: empty_dict)
    created_at: datetime = Field(default_factory=utc_now)
    updated_at: datetime = Field(default_factory=utc_now)

    class Config:
        allow_population_by_field_name = True
        json_encoders = {
            datetime: lambda dt: dt.isoformat()
        }

class BotInDB(BotBase):
    """Schema for bot in database"""
    id: ObjectId = Field(alias="_id")

    class Config:
        allow_population_by_field_name = True
        json_encoders = {
            ObjectId: str,
            datetime: lambda dt: dt.isoformat()
        }

class BotResponse(BaseModel):
    """Response schema for bot operations"""
    result: bool = True
    data: Optional[Dict[str, Any]] = None

class ImportResponse(BaseModel):
    """Response schema for import operations"""
    num_intents_created: int
    num_entities_created: int

class ExportData(BaseModel):
    """Schema for exported data"""
    intents: List[Dict[str, Any]] = Field(default_factory=lambda: empty_list)
    entities: List[Dict[str, Any]] = Field(default_factory=lambda: empty_list)