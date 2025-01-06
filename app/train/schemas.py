from pydantic import BaseModel, Field
from typing import List, Dict, Any

def empty_list() -> List[Any]:
    return []

class TrainingData(BaseModel):
    """Schema for training data"""
    data: List[Dict[str, Any]] = Field(default_factory=lambda: empty_list)

class TrainingResponse(BaseModel):
    """Schema for training response"""
    result: bool 