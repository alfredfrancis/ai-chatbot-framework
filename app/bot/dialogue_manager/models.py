from typing import Optional, Dict, List, Any, Text
from datetime import datetime, UTC
from copy import deepcopy
from dataclasses import dataclass
from app.admin.intents.schemas import Intent


@dataclass
class ApiDetailsModel:
    url: str
    request_type: str
    headers: List[Dict[str, str]]
    is_json: bool = False
    json_data: str = "{}"

    def get_headers(self) -> Dict[str, str]:
        headers = {}
        for header in self.headers:
            headers[header["headerKey"]] = header["headerValue"]
        return headers


@dataclass
class ParameterModel:
    name: str
    required: bool = False
    type: Optional[str] = None
    prompt: Optional[str] = None


@dataclass
class IntentModel:
    name: str
    intent_id: str
    speech_response: str
    user_defined: bool = True
    api_trigger: bool = False
    api_details: Optional[ApiDetailsModel] = None
    parameters: List[ParameterModel] = None

    def __post_init__(self):
        if self.parameters is None:
            self.parameters = []

    @classmethod
    def from_db(cls, db_intent: Intent):
        """Convert database Intent model to domain Intent model"""
        api_details = None
        if db_intent.apiDetails:
            api_details = ApiDetailsModel(
                url=db_intent.apiDetails.url,
                request_type=db_intent.apiDetails.requestType,
                headers=db_intent.apiDetails.headers,
                is_json=db_intent.apiDetails.isJson,
                json_data=db_intent.apiDetails.jsonData,
            )

        parameters = []
        if db_intent.parameters:
            parameters = [
                ParameterModel(
                    name=p.name,
                    required=p.required,
                    type=p.type,
                    prompt=p.prompt,
                )
                for p in db_intent.parameters
            ]

        return cls(
            name=db_intent.name,
            intent_id=db_intent.intentId,
            speech_response=db_intent.speechResponse,
            user_defined=db_intent.userDefined,
            api_trigger=db_intent.apiTrigger,
            api_details=api_details,
            parameters=parameters,
        )


class ChatModel:
    def __init__(
        self,
        input_text: str,
        context: Optional[Dict] = None,
        intent: Optional[Dict] = None,
        extracted_parameters: Optional[Dict] = None,
        missing_parameters: Optional[List[str]] = None,
        complete: bool = False,
        speech_response: Optional[List[str]] = None,
        current_node: str = "",
        parameters: Optional[List[Dict[str, Any]]] = None,
        owner: str = "",
        date: Optional[str] = None,
    ):
        self.input_text = input_text
        self.context = context or {}
        self.intent = intent or {}
        self.nlu = {}
        self.extracted_parameters = extracted_parameters or {}
        self.missing_parameters = missing_parameters or []
        self.complete = complete
        self.speech_response = speech_response or []
        self.current_node = current_node
        self.parameters = parameters or []
        self.owner = owner
        self.date = date or datetime.now(UTC).isoformat()

    @classmethod
    def from_json(cls, request_json: Dict):
        return cls(
            input_text=request_json.get("input", ""),
            context=request_json.get("context", {}),
            intent=request_json.get("intent", {}),
            extracted_parameters=request_json.get("extractedParameters", {}),
            missing_parameters=request_json.get("missingParameters", []),
            complete=request_json.get("complete", False),
            speech_response=request_json.get("speechResponse", []),
            current_node=request_json.get("currentNode", ""),
            parameters=request_json.get("parameters", []),
            owner=request_json.get("owner", ""),
            date=request_json.get("date", None),
        )

    def to_json(self) -> Dict:
        return {
            "input": self.input_text,
            "context": self.context,
            "intent": self.intent,
            "nlu": self.nlu,
            "extractedParameters": self.extracted_parameters,
            "missingParameters": self.missing_parameters,
            "complete": self.complete,
            "speechResponse": self.speech_response,
            "currentNode": self.current_node,
            "parameters": self.parameters,
            "owner": self.owner,
            "date": self.date,
        }

    def clone(self):
        return deepcopy(self)

    def reset(self):
        self.complete = False
        self.intent = {}
        self.missing_parameters = []
        self.extracted_parameters = {}
        self.parameters = []
        self.current_node = {}
        self.speech_response = {}


class UserMessage:
    def __init__(
        self, thread_id: str, text: Text, context: Dict, channel: Text = "rest"
    ):
        self.thread_id = thread_id
        self.text = text
        self.channel = channel
        self.context = context

    def to_dict(self) -> Dict:
        return {
            "thread_id": self.thread_id,
            "text": self.text,
            "channel": self.channel,
            "context": self.context,
        }

    @classmethod
    def from_dict(cls, data: Dict) -> "UserMessage":
        return cls(
            thread_id=data["thread_id"],
            text=data["text"],
            context=data["context"],
            channel=data.get("channel", "rest"),
        )
