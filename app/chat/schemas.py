from pydantic import BaseModel, Field
from typing import Dict, Any, List
from datetime import datetime, UTC

def empty_dict() -> Dict[str, Any]:
    return {}

def empty_list() -> List[Any]:
    return []

def utc_now() -> str:
    """Get current UTC datetime as ISO format string"""
    return datetime.now(UTC).isoformat()

class ChatRequest(BaseModel):
    """Schema for chat request"""
    input: str
    context: Dict[str, Any] = Field(default_factory=lambda: empty_dict)
    intent: Dict[str, Any] = Field(default_factory=lambda: empty_dict)
    extractedParameters: Dict[str, Any] = Field(default_factory=lambda: empty_dict)
    missingParameters: List[str] = Field(default_factory=lambda: empty_list)
    complete: bool = False
    speechResponse: List[str] = Field(default_factory=lambda: empty_list)
    currentNode: str = ""
    parameters: List[Dict[str, Any]] = Field(default_factory=lambda: empty_list)
    owner: str = ""
    date: str = Field(default_factory=utc_now)

    class Config:
        allow_population_by_field_name = True

class ChatResponse(BaseModel):
    """Schema for chat response"""
    input: str
    context: Dict[str, Any] = Field(default_factory=lambda: empty_dict)
    intent: Dict[str, Any] = Field(default_factory=lambda: empty_dict)
    extractedParameters: Dict[str, Any] = Field(default_factory=lambda: empty_dict)
    missingParameters: List[str] = Field(default_factory=lambda: empty_list)
    complete: bool = False
    speechResponse: List[str] = Field(default_factory=lambda: empty_list)
    currentNode: str = ""
    parameters: List[Dict[str, Any]] = Field(default_factory=lambda: empty_list)
    owner: str = ""
    date: str = Field(default_factory=utc_now)

    class Config:
        allow_population_by_field_name = True

class ErrorResponse(BaseModel):
    """Schema for error response"""
    error: str 