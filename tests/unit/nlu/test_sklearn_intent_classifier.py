import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '../../../'))

import pytest
import numpy as np
from unittest.mock import Mock, patch, MagicMock
from app.bot.nlu.intent_classifiers.sklearn_intent_classifer import SklearnIntentClassifier


class TestSklearnIntentClassifier:
    def test_init(self):
        """Test SklearnIntentClassifier initialization."""
        classifier = SklearnIntentClassifier()
        assert classifier.model is None

    @patch("sklearn.model_selection.GridSearchCV")
    @patch("sklearn.svm.SVC")
    def test_train(self, mock_svc, mock_grid_search, mock_spacy_load, sample_training_data):
        """Test training the classifier."""
        # Setup mocks
        mock_classifier = Mock()
        mock_classifier.best_estimator_ = Mock()
        mock_grid_search.return_value = mock_classifier

        classifier = SklearnIntentClassifier()

        # Mock spacy doc with vector
        mock_doc = Mock()
        mock_doc.vector = np.array([0.1, 0.2, 0.3])
        for example in sample_training_data:
            example["spacy_doc"] = mock_doc

        with patch("os.path.exists", return_value=True), \
             patch("os.makedirs"):
            classifier.train(sample_training_data, "/tmp/model")

        assert classifier.model is not None
        mock_grid_search.assert_called_once()

    def test_train_with_empty_text(self, mock_spacy_load):
        """Test training with empty text."""
        classifier = SklearnIntentClassifier()
        mock_doc = Mock()
        mock_doc.vector = np.array([0.1, 0.2, 0.3])
        training_data = [{"text": "", "intent": "greet", "spacy_doc": mock_doc}]

        with patch("sklearn.model_selection.GridSearchCV") as mock_grid:
            mock_grid.return_value = Mock()
            with patch("numpy.stack", side_effect=ValueError("need at least one array to stack")):
                try:
                    classifier.train(training_data, "/tmp/model")
                except ValueError:
                    pass  # Expected

        # Should not process empty text
        assert classifier.model is None

    @patch("cloudpickle.load")
    def test_load_success(self, mock_load, mock_cloudpickle_dump_load):
        """Test successful model loading."""
        mock_load.return_value = Mock()
        classifier = SklearnIntentClassifier()

        result = classifier.load("/tmp/model")
        assert result is True
        assert classifier.model is not None

    @patch("os.path.join")
    @patch("builtins.open", new_callable=MagicMock)
    def test_load_failure(self, mock_open, mock_join):
        """Test model loading failure."""
        mock_join.return_value = "/tmp/model/sklearn_intent_model.hd5"
        mock_open.side_effect = IOError("File not found")

        classifier = SklearnIntentClassifier()
        result = classifier.load("/tmp/model")

        assert result is False
        assert classifier.model is None

    def test_get_spacy_embedding(self, mock_spacy_load):
        """Test spacy embedding extraction."""
        classifier = SklearnIntentClassifier()
        mock_doc = Mock()
        mock_doc.vector = np.array([0.1, 0.2, 0.3])

        result = classifier.get_spacy_embedding(mock_doc)
        np.testing.assert_array_equal(result, np.array([0.1, 0.2, 0.3]))

    def test_predict_proba(self, mock_spacy_load):
        """Test probability prediction."""
        classifier = SklearnIntentClassifier()
        classifier.model = Mock()
        classifier.model.classes_ = ["greet", "goodbye"]
        classifier.model.predict_proba.return_value = np.array([[0.8, 0.2]])

        mock_doc = Mock()
        mock_doc.vector = np.array([0.1, 0.2, 0.3])
        message = {"spacy_doc": mock_doc}

        intents, probabilities = classifier.predict_proba(message)

        assert len(intents) == 1
        assert len(probabilities) == 1

    def test_process_with_model(self, mock_spacy_load):
        """Test processing with trained model."""
        classifier = SklearnIntentClassifier()
        classifier.model = Mock()
        classifier.model.classes_ = ["greet", "goodbye"]
        classifier.model.predict_proba.return_value = np.array([[0.8, 0.2]])

        mock_doc = Mock()
        mock_doc.vector = np.array([0.1, 0.2, 0.3])
        message = {"text": "Hello", "spacy_doc": mock_doc}

        result = classifier.process(message)

        assert "intent" in result
        assert "intent_ranking" in result
        assert result["intent"]["intent"] == "greet"
        assert result["intent"]["confidence"] == 0.8

    def test_process_without_text(self):
        """Test processing without text."""
        classifier = SklearnIntentClassifier()
        message = {"other": "data"}

        result = classifier.process(message)
        assert result == message

    def test_process_without_spacy_doc(self):
        """Test processing without spacy_doc."""
        classifier = SklearnIntentClassifier()
        message = {"text": "Hello"}

        result = classifier.process(message)
        assert result == message

    def test_process_without_model(self, mock_spacy_load):
        """Test processing without trained model."""
        classifier = SklearnIntentClassifier()
        mock_doc = Mock()
        mock_doc.vector = np.array([0.1, 0.2, 0.3])
        message = {"text": "Hello", "spacy_doc": mock_doc}

        result = classifier.process(message)

        assert result["intent"]["name"] is None
        assert result["intent"]["confidence"] == 0.0
        assert result["intent_ranking"] == []
