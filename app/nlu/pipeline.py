from abc import ABC, abstractmethod
from typing import Dict, Any, List, Optional
import os

from app import spacy_tokenizer


class NLUComponent(ABC):
    """Abstract base class for NLU pipeline components."""
    
    @abstractmethod
    def train(self, training_data: List[Dict[str, Any]], model_path: str) -> None:
        """Train the component with given training data and save to model_path."""
        pass
    
    @abstractmethod
    def load(self, model_path: str) -> bool:
        """Load the component from given model path."""
        pass
    
    @abstractmethod
    def process(self, message: Dict[str, Any]) -> Dict[str, Any]:
        """Process a message and return the extracted information."""
        pass

class NLUPipeline:
    """Main NLU pipeline that manages components and their execution order."""
    
    def __init__(self, components: Optional[List[NLUComponent]] = None):
        """Initialize NLU pipeline with optional list of components."""
        self.components = components or []
    
    def add_component(self, component: NLUComponent) -> None:
        """Add a component to the pipeline."""
        self.components.append(component)
    
    def train(self, training_data: List[Dict[str, Any]], model_path: str) -> None:
        """Train all components in the pipeline."""
        if not os.path.exists(model_path):
            os.makedirs(model_path)
            
        for component in self.components:
            component.train(training_data, model_path)
    
    def load(self, model_path: str) -> bool:
        """Load all components from model path."""
        success = True
        for component in self.components:
            if not component.load(model_path):
                success = False
        return success
    
    def process(self, message: Dict[str, Any]) -> Dict[str, Any]:
        """Process message through all components in sequence."""
        for component in self.components:
            message = component.process(message)
        return message

class IntentClassifier(NLUComponent):
    """Intent classification wrapper component."""
    
    def __init__(self):
        from app.nlu.classifiers.sklearn_intent_classifer import SklearnIntentClassifier
        self.classifier = SklearnIntentClassifier()
    
    def train(self, training_data: List[Dict[str, Any]], model_path: str) -> None:
        X = []
        y = []
        for example in training_data:
            if example.get("text", "").strip() == "":
                continue
            X.append(example.get("text"))
            y.append(example.get("intent"))
        
        self.classifier.train(X, y, outpath=model_path)
    
    def load(self, model_path: str) -> bool:
        return self.classifier.load(model_path)
    
    def process(self, message: Dict[str, Any]) -> Dict[str, Any]:
        if not message.get("text"):
            return message
            
        predicted, _ = self.classifier.process(message["text"])
        message["intent"] = predicted
        return message

class EntityExtractor(NLUComponent):
    """Entity extraction wrapper component."""
    
    def __init__(self, synonyms: Optional[Dict[str, str]] = None):
        from app.nlu.entity_extractors.crf_entity_extractor import CRFEntityExtractor
        self.extractor = CRFEntityExtractor(spacy_tokenizer, synonyms or {})
    
    def train(self, training_data: List[Dict[str, Any]], model_path: str) -> None:
        # Group training data by intent
        intent_data = {}
        for example in training_data:
            intent = example.get("intent")
            if intent not in intent_data:
                intent_data[intent] = []
            intent_data[intent].append(example)
        
        # Train model for each intent
        for intent_id, examples in intent_data.items():
            ner_training_data = self.extractor.json2crf(examples)
            self.extractor.train(ner_training_data, intent_id)
    
    def load(self, model_path: str) -> bool:
        # Entity extractor loads models on demand per intent
        return True
    
    def process(self, message: Dict[str, Any]) -> Dict[str, Any]:
        if not message.get("text") or not message.get("intent", {}).get("intent"):
            return message
            
        intent_id = message["intent"]["intent"]
        entities = self.extractor.predict(intent_id, message["text"])
        message["entities"] = entities
        return message 