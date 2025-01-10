from typing import Any, Dict, List, Optional
from app.bot.nlu.pipeline import NLUComponent

class EntityExtractor(NLUComponent):
    """Entity extraction wrapper component."""
    
    def __init__(self, synonyms: Optional[Dict[str, str]] = None):
        from .crf_entity_extractor import CRFEntityExtractor
        self.extractor = CRFEntityExtractor(synonyms or {})
    
    def train(self, training_data: List[Dict[str, Any]], model_path: str) -> None:
        # Convert all training data to CRF format at once
        ner_training_data = self.extractor.json2crf(training_data)
        # Train a single model for all entities
        self.extractor.train(ner_training_data, "entity_model")
    
    def load(self, model_path: str) -> bool:
        # Load the single entity model
        return self.extractor.load(model_path)
    
    def process(self, message: Dict[str, Any]) -> Dict[str, Any]:
        if not message.get("text") or not message.get("spacy_doc"):
            return message

        entities = self.extractor.predict(message)
        message["entities"] = entities
        return message 