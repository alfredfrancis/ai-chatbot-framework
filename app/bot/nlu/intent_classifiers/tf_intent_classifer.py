import os
import time
import logging
from typing import Dict, Any, List
import cloudpickle
import numpy as np
import spacy
import tensorflow as tf
from sklearn.preprocessing import LabelBinarizer
from tensorflow.python.keras import Sequential
from tensorflow.python.layers.core import Dense
from tensorflow.python.layers.core import Dropout
from app.bot.nlu.pipeline import NLUComponent

np.random.seed(1)

logger = logging.getLogger(__name__)


class TfIntentClassifier(NLUComponent):
    """TensorFlow-based intent classifier that implements NLUComponent interface."""

    INTENT_RANKING_LENGTH = 3
    MODEL_NAME = "tf_intent_model.hd5"
    LABELS_NAME = "labels.pkl"

    def __init__(self):
        self.model = None
        self.nlp = spacy.load("en")
        self.label_encoder = LabelBinarizer()
        self.graph = None

    def train(self, training_data: List[Dict[str, Any]], model_path: str) -> None:
        """Train intent classifier for given training data"""

        def create_model():
            """Define and return tensorflow model."""
            model = Sequential()
            model.add(Dense(256, activation=tf.nn.relu, input_shape=(vocab_size,)))
            model.add(Dropout(0.2))
            model.add(Dense(128, activation=tf.nn.relu))
            model.add(Dropout(0.2))
            model.add(Dense(num_labels, activation=tf.nn.softmax))

            model.compile(
                loss="categorical_crossentropy",
                optimizer="adam",
                metrics=["accuracy"],
            )

            model.summary()
            return model

        # Extract training features
        X = []
        y = []
        for example in training_data:
            if example.get("text", "").strip() == "":
                continue
            X.append(example.get("text"))
            y.append(example.get("intent"))

        # spacy context vector size
        vocab_size = 384

        # create spacy doc vector matrix
        x_train = np.array([list(self.nlp(x).vector) for x in X])

        num_labels = len(set(y))
        self.label_encoder.fit(y)
        y_train = self.label_encoder.transform(y)

        del self.model
        tf.keras.backend.clear_session()
        time.sleep(3)

        self.model = create_model()
        # start training
        self.model.fit(x_train, y_train, shuffle=True, epochs=300, verbose=1)

        if model_path:
            # Save model
            model_file = os.path.join(model_path, self.MODEL_NAME)
            tf.keras.models.save_model(self.model, model_file)
            logger.info(f"TF Model written out to {model_file}")

            # Save label encoder
            labels_file = os.path.join(model_path, self.LABELS_NAME)
            with open(labels_file, "wb") as f:
                cloudpickle.dump(self.label_encoder, f)
            logger.info(f"Labels written out to {labels_file}")

    def load(self, model_path: str) -> bool:
        """Load trained model from given path"""
        try:
            del self.model
            tf.keras.backend.clear_session()

            # Load model
            model_file = os.path.join(model_path, self.MODEL_NAME)
            self.model = tf.keras.models.load_model(model_file, compile=True)
            self.graph = tf.get_default_graph()
            logger.info("TF model loaded")

            # Load label encoder
            labels_file = os.path.join(model_path, self.LABELS_NAME)
            with open(labels_file, "rb") as f:
                self.label_encoder = cloudpickle.load(f)
            logger.info("Labels model loaded")
            return True

        except Exception as e:
            logger.error(f"Error loading model: {e}")
            return False

    def predict_proba(self, message: Dict[str, Any]):
        """Given a message, predict most probable label.
        Returns tuple of sorted indices and probabilities."""
        x_predict = [self.nlp(message.get("text")).vector]
        with self.graph.as_default():
            pred_result = self.model.predict(np.array([x_predict[0]]))
        sorted_indices = np.fliplr(np.argsort(pred_result, axis=1))
        return sorted_indices, pred_result[:, sorted_indices]

    def process(self, message: Dict[str, Any]) -> Dict[str, Any]:
        """Process a message and return the extracted information."""
        if not message.get("text"):
            return message

        intent = {"name": None, "confidence": 0.0}
        intent_ranking = []

        if self.model:
            intents, probabilities = self.predict_proba(message)
            intents = [
                self.label_encoder.classes_[intent] for intent in intents.flatten()
            ]
            probabilities = probabilities.flatten()

            if len(intents) > 0 and len(probabilities) > 0:
                ranking = list(zip(list(intents), list(probabilities)))
                ranking = ranking[: self.INTENT_RANKING_LENGTH]

                intent = {
                    "intent": intents[0],
                    "confidence": float("%.2f" % probabilities[0]),
                }
                intent_ranking = [
                    {"intent": intent_name, "confidence": float("%.2f" % score)}
                    for intent_name, score in ranking
                ]
            else:
                intent = {"name": None, "confidence": 0.0}
                intent_ranking = []

        message["intent"] = intent
        message["intent_ranking"] = intent_ranking
        return message
