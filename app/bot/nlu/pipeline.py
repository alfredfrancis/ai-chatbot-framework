from abc import ABC, abstractmethod
from typing import Dict, Any, List, Optional
import os


class NLUComponent(ABC):
    """Abstract base class for NLU pipeline components."""

    @abstractmethod
    def train(self, training_data: List[Dict[str, Any]], model_path: str) -> None:
        """Train the component with given training data
        and save to model_path."""
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
        for component in self.components:
            if not component.load(model_path):
                return False
        return True

    def process(self, message: Dict[str, Any]) -> Dict[str, Any]:
        """Process message through all components in sequence."""
        for component in self.components:
            message = component.process(message)
        return message
