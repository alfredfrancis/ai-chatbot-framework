from pydantic import BaseModel, Field
from typing import List, Optional, Dict, Any
from datetime import datetime, UTC
from bson import ObjectId

def empty_list() -> List[Any]:
    return []

def empty_dict() -> Dict[str, Any]:
    return {}

def generate_object_id() -> str:
    return str(ObjectId())

def utc_now() -> datetime:
    """Get current UTC datetime with timezone information"""
    return datetime.now(UTC)

class LabeledSentences(BaseModel):
    """Schema for labeled sentences"""
    id: str = Field(default_factory=generate_object_id)
    data: List[str] = Field(default_factory=empty_list)

class Parameter(BaseModel):
    """Parameter schema for intent parameters"""
    id: str = Field(default_factory=generate_object_id)
    name: str
    required: bool = False
    type: Optional[str] = None
    prompt: Optional[str] = None

class ApiDetails(BaseModel):
    """API details schema for intent API triggers"""
    url: str
    requestType: str
    headers: List[Dict[str, str]] = Field(default_factory=empty_list)
    isJson: bool = False
    jsonData: str = "{}"

    def get_headers(self) -> Dict[str, str]:
        headers = {}
        for header in self.headers:
            headers[header["headerKey"]] = header["headerValue"]
        return headers

class IntentBase(BaseModel):
    """Base schema for intent"""
    name: str
    userDefined: bool = True
    intentId: str
    apiTrigger: bool = False
    apiDetails: Optional[ApiDetails] = None
    speechResponse: str
    parameters: List[Parameter] = Field(default_factory=empty_list)
    labeledSentences: List[LabeledSentences] = Field(default_factory=empty_list)
    trainingData: List[Dict[str, Any]] = Field(default_factory=empty_list)
    created_at: datetime = Field(default_factory=utc_now)
    updated_at: datetime = Field(default_factory=utc_now)

    model_config = {
        "populate_by_name": True,
        "json_encoders": {
            datetime: lambda dt: dt.isoformat()
        }
    }

class IntentCreate(IntentBase):
    """Schema for creating an intent"""
    pass

class IntentUpdate(IntentBase):
    """Schema for updating an intent"""
    pass

class IntentInDB(IntentBase):
    """Schema for intent in database"""
    id: str = Field(alias="_id", default_factory=generate_object_id)

    model_config = {
        "populate_by_name": True,
        "json_encoders": {
            ObjectId: str,
            datetime: lambda dt: dt.isoformat()
        }
    }

class IntentResponse(BaseModel):
    """Schema for intent response"""
    status: str
    data: Optional[Dict[str, Any]] = None
    message: Optional[str] = None 