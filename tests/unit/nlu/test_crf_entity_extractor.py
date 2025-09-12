
import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '../../../'))

import pytest
from unittest.mock import Mock, patch, MagicMock
from app.bot.nlu.entity_extractors.crf_entity_extractor import CRFEntityExtractor

class TestCRFEntityExtractor:
    class Token:
        def __init__(self, i, text, pos_, tag_):
            self.i = i
            self.text = text
            self.pos_ = pos_
            self.tag_ = tag_
            self.vector = [0.1, 0.2, 0.3]  # Add vector attribute for spacy compatibility

    def test_init(self):
        """Test CRFEntityExtractor initialization."""
        extractor = CRFEntityExtractor()
        assert extractor.tagger is None

    @patch("pycrfsuite.Trainer")
    def test_train(self, mock_trainer, mock_spacy_load, sample_training_data):
        """Test training the CRF extractor."""
        # Setup mocks
        mock_train_instance = Mock()
        mock_trainer.return_value = mock_train_instance

        extractor = CRFEntityExtractor()

        mock_doc = MagicMock()
        mock_doc.__iter__.return_value = iter([
            self.Token(0, "Hello", "NOUN", "UH"),
            self.Token(1, "world", "NN", "NN")
        ])
        mock_doc.char_span.return_value = [self.Token(0, "Hello", "NOUN", "UH")]

        for example in sample_training_data:
            example["spacy_doc"] = mock_doc

        # Ensure /tmp/model exists
        if not os.path.exists("/tmp/model"):
            os.makedirs("/tmp/model")

        extractor.train(sample_training_data, "/tmp/model")
        mock_train_instance.train.assert_called_once()

    def test_load_success(self, mock_pycrfsuite_tagger):
        """Test successful model loading."""
        mock_tagger_instance = Mock()
        mock_pycrfsuite_tagger.return_value = mock_tagger_instance

        extractor = CRFEntityExtractor()

        with patch("os.path.join"), \
             patch("builtins.open", new_callable=MagicMock):
            mock_doc = MagicMock()
            mock_doc.__iter__.return_value = iter([
                TestCRFEntityExtractor.Token(0, "Hello", "NOUN", "UH"),
                TestCRFEntityExtractor.Token(1, "world", "NN", "NN")
            ])
            mock_doc.char_span.return_value = [TestCRFEntityExtractor.Token(0, "Hello", "NOUN", "UH")]

    def test_load_failure(self):
        """Test model loading failure."""
        extractor = CRFEntityExtractor()

        mock_tagger = Mock()
        mock_tagger.open.side_effect = IOError("File not found")

        with patch("os.path.join"), \
             patch("pycrfsuite.Tagger", return_value=mock_tagger):
            result = extractor.load("/tmp/model")

        assert result is False

    def test_extract_features(self, mock_spacy_load):
        """Test feature extraction for CRF."""
        extractor = CRFEntityExtractor()

        sent = [("Hello", "UH"), ("world", "NN")]
        features = extractor.extract_features(sent, 0)

        assert "bias" in features
        assert "word.lower=hello" in features
        assert "postag=UH" in features

    def test_sent_to_features(self, mock_spacy_load):
        """Test converting sentence to features."""
        extractor = CRFEntityExtractor()

        sent = [("Hello", "UH"), ("world", "NN")]
        features = extractor.sent_to_features(sent)

        assert len(features) == 2
        assert isinstance(features[0], list)

    def test_sent_to_labels(self, mock_spacy_load):
        """Test extracting labels from sentence."""
        extractor = CRFEntityExtractor()

        sent = [("Hello", "UH", "O"), ("world", "NN", "O")]
        labels = extractor.sent_to_labels(sent)

        assert labels == ["O", "O"]

    def test_process_with_text_and_spacy_doc(self, mock_spacy_load, mock_pycrfsuite_tagger):
        """Test processing message with text and spacy_doc."""
        mock_tagger_instance = Mock()
        mock_tagger_instance.tag.return_value = ["B-PERSON", "O"]
        mock_pycrfsuite_tagger.return_value = mock_tagger_instance

        extractor = CRFEntityExtractor()
        extractor.tagger = mock_tagger_instance

        mock_doc = MagicMock()
        mock_doc.__iter__.return_value = iter([
            self.Token(0, "John", "PROPN", "NNP"),
            self.Token(1, "said", "VERB", "VB")
        ])
        mock_doc.char_span.return_value = [self.Token(0, "John", "PROPN", "NNP")]

        message = {"text": "John said", "spacy_doc": mock_doc}

        result = extractor.process(message)
        assert "entities" in result

    def test_process_without_text(self):
        """Test processing without text."""
        extractor = CRFEntityExtractor()
        message = {"other": "data"}

        result = extractor.process(message)
        assert result == message

    def test_process_without_spacy_doc(self):
        """Test processing without spacy_doc."""
        extractor = CRFEntityExtractor()
        message = {"text": "Hello world"}

        result = extractor.process(message)
        assert result == message
