import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '../../../'))

import pytest
from unittest.mock import Mock, patch
from app.bot.nlu.featurizers.spacy_featurizer import SpacyFeaturizer


class TestSpacyFeaturizer:
    def test_init(self, mock_spacy_load):
        """Test SpacyFeaturizer initialization."""
        featurizer = SpacyFeaturizer("en_core_web_sm")
        assert featurizer.tokenizer is not None
        mock_spacy_load.assert_called_once_with("en_core_web_sm")

    def test_train_with_valid_data(self, mock_spacy_load, sample_training_data):
        """Test training with valid data."""
        featurizer = SpacyFeaturizer("en_core_web_sm")
        mock_doc = Mock()
        mock_doc.vector = [0.1, 0.2, 0.3]
        featurizer.tokenizer.return_value = mock_doc

        featurizer.train(sample_training_data, "/tmp/model")

        # Check that spacy_doc was added to training data
        assert sample_training_data[0]["spacy_doc"] is not None
        assert sample_training_data[1]["spacy_doc"] is not None

    def test_train_with_empty_text(self, mock_spacy_load):
        """Test training with empty text."""
        featurizer = SpacyFeaturizer("en_core_web_sm")
        training_data = [{"text": "", "intent": "greet"}]

        featurizer.train(training_data, "/tmp/model")

        # Should not add spacy_doc for empty text
        assert "spacy_doc" not in training_data[0]

    def test_load(self, mock_spacy_load):
        """Test load method."""
        featurizer = SpacyFeaturizer("en_core_web_sm")
        result = featurizer.load("/tmp/model")
        assert result is True

    def test_process_with_text(self, mock_spacy_load):
        """Test processing message with text."""
        featurizer = SpacyFeaturizer("en_core_web_sm")
        mock_doc = Mock()
        mock_doc.vector = [0.1, 0.2, 0.3]
        featurizer.tokenizer.return_value = mock_doc

        message = {"text": "Hello world"}
        result = featurizer.process(message)

        assert result["spacy_doc"] is not None
        assert result["text"] == "Hello world"

    def test_process_without_text(self, mock_spacy_load):
        """Test processing message without text."""
        featurizer = SpacyFeaturizer("en_core_web_sm")
        message = {"other": "data"}
        result = featurizer.process(message)

        assert result == message
        assert "spacy_doc" not in result

    def test_process_with_empty_text(self, mock_spacy_load):
        """Test processing message with empty text."""
        featurizer = SpacyFeaturizer("en_core_web_sm")
        message = {"text": ""}
        result = featurizer.process(message)

        assert result == message
        assert "spacy_doc" not in result
