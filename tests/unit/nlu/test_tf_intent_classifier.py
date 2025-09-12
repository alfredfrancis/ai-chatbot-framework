import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '../../../'))

import pytest
import numpy as np
from unittest.mock import Mock, patch, MagicMock
from app.bot.nlu.intent_classifiers.tf_intent_classifer import TfIntentClassifier


class TestTfIntentClassifier:
    @patch("tensorflow.keras.models.load_model")
    @patch("tensorflow.keras.backend.clear_session")
    @patch("spacy.load")
    def test_init(self, mock_spacy_load, mock_clear_session, mock_load_model):
        """Test TfIntentClassifier initialization."""
        mock_nlp = Mock()
        mock_spacy_load.return_value = mock_nlp

        classifier = TfIntentClassifier()
        assert classifier.model is None
        assert classifier.nlp is not None
        assert classifier.label_encoder is not None

    @patch("app.bot.nlu.intent_classifiers.tf_intent_classifer.Sequential")
    @patch("app.bot.nlu.intent_classifiers.tf_intent_classifer.Dense")
    @patch("app.bot.nlu.intent_classifiers.tf_intent_classifer.Dropout")
    @patch("tensorflow.keras.backend.clear_session")
    @patch("spacy.load")
    def test_train(self, mock_spacy_load, mock_clear_session, mock_dropout, mock_dense, mock_sequential, sample_training_data):
        """Test training the classifier."""
        # Setup mocks
        mock_nlp = Mock()
        mock_doc = Mock()
        mock_doc.vector = np.array([0.1] * 384)  # Mock embedding vector of size 384
        mock_nlp.return_value = mock_doc
        mock_spacy_load.return_value = mock_nlp

        mock_model = Mock()
        mock_model.fit = Mock(return_value=None)
        mock_sequential.return_value = mock_model

        classifier = TfIntentClassifier()

        # One-hot encode intent labels for training data
        intents = [example["intent"] for example in sample_training_data]
        unique_intents = sorted(set(intents))
        intent_to_index = {intent: idx for idx, intent in enumerate(unique_intents)}
        y_train = np.eye(len(unique_intents))[np.array([intent_to_index[i] for i in intents])]

        # Patch classifier.label_encoder to return the correct one-hot encoded labels
        classifier.label_encoder = Mock()
        classifier.label_encoder.transform.side_effect = lambda labels: np.eye(len(unique_intents))[np.array([intent_to_index[l] for l in labels])]
        classifier.label_encoder.classes_ = np.array(unique_intents)

        with patch("os.path.exists", return_value=True), \
             patch("os.makedirs"), \
             patch("tensorflow.keras.models.save_model"):
            classifier.train(sample_training_data, "/tmp/model")

        assert classifier.model is not None
        classifier.model.fit.assert_called_once()



    @patch("spacy.load")
    def test_load_failure(self, mock_spacy_load):
        """Test model loading failure."""
        mock_nlp = Mock()
        mock_spacy_load.return_value = mock_nlp

        classifier = TfIntentClassifier()

        with patch("os.path.join"), \
             patch("builtins.open", side_effect=IOError("File not found")), \
             patch("tensorflow.compat.v1.get_default_graph") as mock_get_graph:
            mock_get_graph.return_value = Mock()
            result = classifier.load("/tmp/model")

        assert result is False

    @patch("tensorflow.keras.backend.clear_session")
    @patch("spacy.load")
    def test_predict_proba(self, mock_spacy_load, mock_clear_session):
        """Test probability prediction."""
        mock_nlp = Mock()
        mock_doc = Mock()
        mock_doc.vector = np.array([0.1] * 384)  # Spacy vector size
        mock_nlp.return_value = mock_doc
        mock_spacy_load.return_value = mock_nlp

        classifier = TfIntentClassifier()
        classifier.model = Mock()
        classifier.model.predict.return_value = np.array([[0.8, 0.2]])
        classifier.label_encoder = Mock()
        classifier.label_encoder.classes_ = ["greet", "goodbye"]
        classifier.graph = Mock()
        classifier.graph.as_default.return_value.__enter__ = Mock()
        classifier.graph.as_default.return_value.__exit__ = Mock()

        message = {"text": "Hello"}

        intents, probabilities = classifier.predict_proba(message)

        assert len(intents) == 1
        assert len(probabilities) == 1

    @patch("tensorflow.keras.backend.clear_session")
    @patch("spacy.load")
    def test_process_with_model(self, mock_spacy_load, mock_clear_session):
        """Test processing with trained model."""
        mock_nlp = Mock()
        mock_doc = Mock()
        mock_doc.vector = np.array([0.1] * 384)  # Spacy vector size
        mock_nlp.return_value = mock_doc
        mock_spacy_load.return_value = mock_nlp

        classifier = TfIntentClassifier()
        classifier.model = Mock()
        classifier.model.predict.return_value = np.array([[0.8, 0.2]])
        classifier.label_encoder = Mock()
        classifier.label_encoder.classes_ = ["greet", "goodbye"]
        classifier.graph = Mock()
        classifier.graph.as_default.return_value.__enter__ = Mock()
        classifier.graph.as_default.return_value.__exit__ = Mock()

        message = {"text": "Hello"}

        result = classifier.process(message)

        assert "intent" in result
        assert "intent_ranking" in result
        assert result["intent"]["intent"] == "greet"
        assert result["intent"]["confidence"] == 0.8

    @patch("spacy.load")
    def test_process_without_text(self, mock_spacy_load):
        """Test processing without text."""
        mock_nlp = Mock()
        mock_spacy_load.return_value = mock_nlp

        classifier = TfIntentClassifier()
        message = {"other": "data"}

        result = classifier.process(message)
        assert result == message

    @patch("tensorflow.keras.backend.clear_session")
    @patch("spacy.load")
    def test_process_without_model(self, mock_spacy_load, mock_clear_session):
        """Test processing without trained model."""
        mock_nlp = Mock()
        mock_spacy_load.return_value = mock_nlp

        classifier = TfIntentClassifier()
        message = {"text": "Hello"}

        result = classifier.process(message)

        assert result["intent"]["name"] is None
        assert result["intent"]["confidence"] == 0.0
        assert result["intent_ranking"] == []
