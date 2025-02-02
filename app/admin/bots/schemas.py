from pydantic import BaseModel, Field
from typing import Optional
from app.database import ObjectIdField
from datetime import datetime


class TraditionalNLUSettings(BaseModel):
    """Settings for traditional ML-based NLU pipeline"""

    intent_detection_threshold: float = 0.75
    entity_detection_threshold: float = 0.65
    use_spacy: bool = True


class LLMSettings(BaseModel):
    """Settings for LLM-based NLU pipeline"""

    base_url: str = "http://127.0.0.1:11434/v1"
    api_key: str = "ollama"
    model_name: str = "llama2:13b-chat"
    max_tokens: int = 4096
    temperature: float = 0.7


class NLUConfiguration(BaseModel):
    """Configuration for Natural Language Understanding"""

    pipeline_type: str = "traditional"  # Either 'traditional' or 'llm'
    traditional_settings: TraditionalNLUSettings = TraditionalNLUSettings()
    llm_settings: LLMSettings = LLMSettings()


class Bot(BaseModel):
    """Base schema for bot"""

    id: ObjectIdField = Field(validation_alias="_id", default=None)
    name: str
    nlu_config: NLUConfiguration = NLUConfiguration()
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None
