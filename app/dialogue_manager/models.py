from typing import Optional, Dict, List, Any
from datetime import datetime
from copy import deepcopy

class ChatModel:
    def __init__(self,
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
                 date: Optional[str] = None):
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
        self.date = date or datetime.utcnow().isoformat()

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
            date=request_json.get("date", None)
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
            "date": self.date
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