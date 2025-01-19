from typing import Any, Dict, List
from app.bot.nlu.pipeline import NLUComponent


class SpacyFeaturizer(NLUComponent):
    """Spacy featurizer component that processes text and adds spacy features."""

    def __init__(self, model_name: str):
        import spacy

        self.tokenizer = spacy.load(model_name)

    def train(self, training_data: List[Dict[str, Any]], model_path: str) -> None:
        for example in training_data:
            if example.get("text", "").strip() == "":
                continue
            example["spacy_doc"] = self.tokenizer(example["text"])

    def load(self, model_path: str) -> bool:
        """Nothing to load for spacy featurizer."""
        return True

    def process(self, message: Dict[str, Any]) -> Dict[str, Any]:
        """Process text with spacy and add doc to message."""
        if not message.get("text"):
            return message

        doc = self.tokenizer(message["text"])
        message["spacy_doc"] = doc
        return message
