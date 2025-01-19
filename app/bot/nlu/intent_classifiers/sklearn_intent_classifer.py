import os
from typing import Dict, Any, List
import cloudpickle
import numpy as np
from app.bot.nlu.pipeline import NLUComponent
import logging

logger = logging.getLogger(__name__)


class SklearnIntentClassifier(NLUComponent):
    """Sklearn-based intent classifier that implements NLUComponent interface."""

    INTENT_RANKING_LENGTH = 3
    MODEL_NAME = "sklearn_intent_model.hd5"

    def __init__(self):
        self.model = None

    def get_spacy_embedding(self, spacy_doc):
        """
        perform basic cleaning,tokenization and lemmatization
        :param sentence:
        :return list of clean tokens:
        """
        return np.array(spacy_doc.vector)

    def train(self, training_data: List[Dict[str, Any]], model_path: str) -> None:
        """Train intent classifier for given training data"""
        from sklearn.model_selection import GridSearchCV
        from sklearn.svm import SVC

        X = []
        y = []
        for example in training_data:
            if example.get("text", "").strip() == "":
                continue
            X.append(example.get("spacy_doc"))
            y.append(example.get("intent"))

        X = np.stack([self.get_spacy_embedding(example) for example in X])

        _, counts = np.unique(y, return_counts=True)
        cv_splits = max(2, min(5, np.min(counts) // 5))

        tuned_parameters = [
            {"C": [1, 2, 5, 10, 20, 100], "gamma": [0.1], "kernel": ["linear"]}
        ]

        classifier = GridSearchCV(
            SVC(C=1, probability=True, class_weight="balanced"),
            param_grid=tuned_parameters,
            n_jobs=-1,
            cv=cv_splits,
            scoring="f1_weighted",
            verbose=1,
        )

        classifier.fit(X, y)

        if model_path:
            path = os.path.join(model_path, self.MODEL_NAME)
            with open(path, "wb") as f:
                cloudpickle.dump(classifier.best_estimator_, f)
        logger.info("Training completed & model written out to {}".format(path))

        self.model = classifier.best_estimator_

    def load(self, model_path: str) -> bool:
        """Load trained model from given path"""
        try:
            path = os.path.join(model_path, self.MODEL_NAME)
            with open(path, "rb") as f:
                self.model = cloudpickle.load(f)
            return True
        except IOError:
            return False

    def predict_proba(self, X):
        """Given a bow vector of an input text, predict most probable label.
         Returns only the most likely label.

        :param X: bow of input text
        :return: tuple of first, the most probable label
        and second, its probability"""

        pred_result = self.model.predict_proba(
            [self.get_spacy_embedding(X.get("spacy_doc"))]
        )
        # sort the probabilities retrieving the indices of the elements
        sorted_indices = np.fliplr(np.argsort(pred_result, axis=1))
        return sorted_indices, pred_result[:, sorted_indices]

    def process(self, message: Dict[str, Any]) -> Dict[str, Any]:
        """Process a message and return the extracted information."""
        if not message.get("text") or not message.get("spacy_doc"):
            return message

        intent = {"name": None, "confidence": 0.0}
        intent_ranking = []

        if self.model:
            intents, probabilities = self.predict_proba(message)
            intents = [self.model.classes_[intent] for intent in intents.flatten()]
            probabilities = probabilities.flatten()

            if len(intents) > 0 and len(probabilities) > 0:
                ranking = list(zip(list(intents), list(probabilities)))
                ranking = ranking[: self.INTENT_RANKING_LENGTH]

                intent = {"intent": intents[0], "confidence": probabilities[0]}
                intent_ranking = [
                    {"intent": intent_name, "confidence": score}
                    for intent_name, score in ranking
                ]
            else:
                intent = {"name": None, "confidence": 0.0}
                intent_ranking = []

        message["intent"] = intent
        message["intent_ranking"] = intent_ranking
        return message
