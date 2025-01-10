from typing import Any, Dict, List
from app.bot.nlu.pipeline import NLUComponent

class IntentClassifier(NLUComponent):
    """Intent classification wrapper component."""
    
    def __init__(self):
        from .sklearn_intent_classifer import SklearnIntentClassifier
        self.classifier = SklearnIntentClassifier()
    
    def train(self, training_data: List[Dict[str, Any]], model_path: str) -> None:
        self.classifier.train(training_data, outpath=model_path)
    
    def load(self, model_path: str) -> bool:
        return self.classifier.load(model_path)
    
    def process(self, message: Dict[str, Any]) -> Dict[str, Any]:
        if not message.get("text") or not message.get("spacy_doc"):
            return message
            
        predicted, _ = self.classifier.process(message)
        message["intent"] = predicted
        return message