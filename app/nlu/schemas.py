from pydantic import BaseModel, Field
from typing import Dict, Any, Optional, List

def empty_list() -> List[Any]:
    return []

class BuildModelResponse(BaseModel):
    """Response schema for build_models endpoint"""
    result: bool

class TrainingData(BaseModel):
    """Schema for training data"""
    text: str
    entities: List[Dict[str, Any]] = Field(default_factory=lambda: empty_list)

class PredictionResponse(BaseModel):
    """Schema for NLU prediction response"""
    intent: Dict[str, Any]
    entities: List[Dict[str, Any]] = Field(default_factory=lambda: empty_list)
    originalText: str
    possibleIntents: Optional[List[Dict[str, float]]] = Field(default_factory=lambda: empty_list) 