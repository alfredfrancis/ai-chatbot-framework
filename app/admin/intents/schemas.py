from app.database import ObjectIdField
from pydantic import BaseModel, Field, ConfigDict
from typing import List, Optional, Dict, Any
from bson import ObjectId


def generate_object_id() -> str:
    return str(ObjectId())


class LabeledSentences(BaseModel):
    """Schema for labeled sentences"""

    id: ObjectIdField = Field(default_factory=generate_object_id)
    data: List[str] = []

    model_config = ConfigDict(arbitrary_types_allowed=True)


class Parameter(BaseModel):
    """Parameter schema for intent parameters"""

    id: ObjectIdField = Field(default_factory=generate_object_id)
    name: str
    required: bool = False
    type: Optional[str] = None
    prompt: Optional[str] = None

    model_config = ConfigDict(arbitrary_types_allowed=True)


class ApiDetails(BaseModel):
    """API details schema for intent API triggers"""

    url: str
    requestType: str
    headers: List[Dict[str, str]] = []
    isJson: bool = False
    jsonData: str = "{}"

    def get_headers(self) -> Dict[str, str]:
        headers = {}
        for header in self.headers:
            headers[header["headerKey"]] = header["headerValue"]
        return headers


class Intent(BaseModel):
    """Base schema for intent"""

    id: ObjectIdField = Field(validation_alias="_id", default=None)
    name: str
    userDefined: bool = True
    intentId: str
    apiTrigger: bool = False
    apiDetails: Optional[ApiDetails] = None
    speechResponse: str
    parameters: List[Parameter] = []
    labeledSentences: List[LabeledSentences] = []
    trainingData: List[Dict[str, Any]] = []

    model_config = ConfigDict(arbitrary_types_allowed=True)
