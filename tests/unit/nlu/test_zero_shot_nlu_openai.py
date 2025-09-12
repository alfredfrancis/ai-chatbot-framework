import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '../../../'))

import pytest
from unittest.mock import Mock, patch, MagicMock
from app.bot.nlu.llm.zero_shot_nlu_openai import ZeroShotNLUOpenAI


class TestZeroShotNLUOpenAI:
    @patch("app.bot.nlu.llm.zero_shot_nlu_openai.Environment")
    @patch("app.bot.nlu.llm.zero_shot_nlu_openai.FileSystemLoader")
    def test_init(self, mock_loader, mock_env, mock_openai_chain):
        """Test ZeroShotNLUOpenAI initialization."""
        mock_llm, mock_prompt, mock_parser = mock_openai_chain

        # Mock environment and template
        mock_environment = Mock()
        mock_env.return_value = mock_environment
        mock_template = Mock()
        mock_template.render.return_value = "system prompt"
        mock_environment.get_template.return_value = mock_template

        # Mock chain
        mock_chain = Mock()
        mock_prompt.return_value = mock_chain

        intents = ["greet", "goodbye"]
        entities = ["person", "location"]

        nlu = ZeroShotNLUOpenAI(intents=intents, entities=entities)

        assert nlu.intents == intents
        assert nlu.entities == entities
        assert nlu.llm is not None
        assert nlu.chain is not None

    def test_train(self, mock_openai_chain):
        """Test train method (should do nothing)."""
        mock_llm, mock_prompt, mock_parser = mock_openai_chain
        nlu = ZeroShotNLUOpenAI()
        # Should not raise any exception
        nlu.train([], "/tmp/model")

    def test_load(self, mock_openai_chain):
        """Test load method."""
        mock_llm, mock_prompt, mock_parser = mock_openai_chain
        nlu = ZeroShotNLUOpenAI()
        result = nlu.load("/tmp/model")
        assert result is True

    def test_process_success(self, mock_openai_chain):
        """Test successful message processing."""
        mock_llm, mock_prompt, mock_parser = mock_openai_chain

        # Mock the chain directly
        mock_chain = Mock()
        mock_chain.invoke = Mock(return_value={
            "intent": "greet",
            "entities": {"person": "John", "location": None}
        })
        mock_prompt.return_value = mock_chain

        nlu = ZeroShotNLUOpenAI(intents=["greet"], entities=["person", "location"])
        # Mock the chain after initialization
        nlu.chain = mock_chain

        message = {"text": "Hello John"}

        result = nlu.process(message)

        assert "intent" in result
        assert result["intent"]["intent"] == "greet"
        assert result["intent"]["confidence"] == 1.0
        assert "intent_ranking" in result
        assert "entities" in result
        assert result["entities"]["person"] == "John"
        assert "location" not in result["entities"]  # None values should be filtered out

    @patch("app.bot.nlu.llm.zero_shot_nlu_openai.Environment")
    @patch("app.bot.nlu.llm.zero_shot_nlu_openai.FileSystemLoader")
    def test_process_without_text(self, mock_loader, mock_env, mock_openai_chain):
        """Test processing message without text."""
        mock_llm, mock_prompt, mock_parser = mock_openai_chain

        # Setup mocks
        mock_environment = Mock()
        mock_env.return_value = mock_environment
        mock_template = Mock()
        mock_template.render.return_value = "system prompt"
        mock_environment.get_template.return_value = mock_template

        mock_chain = Mock()
        mock_prompt.return_value = mock_chain

        nlu = ZeroShotNLUOpenAI()
        message = {"other": "data"}

        result = nlu.process(message)

        # Should log warning and return original message
        assert result == message
        assert "intent" not in result

    def test_process_with_exception(self, mock_openai_chain):
        """Test processing with exception handling."""
        mock_llm, mock_prompt, mock_parser = mock_openai_chain

        # Mock the chain directly
        mock_chain = Mock()
        mock_chain.invoke = Mock(side_effect=Exception("API Error"))
        mock_prompt.return_value = mock_chain

        nlu = ZeroShotNLUOpenAI()
        # Mock the chain after initialization
        nlu.chain = mock_chain

        message = {"text": "Hello world"}

        result = nlu.process(message)

        assert result["intent"]["intent"] is None
        assert result["intent"]["confidence"] == 0.0
        assert result["intent_ranking"] == []
        assert result["entities"] == {}

    def test_process_with_no_intent(self, mock_openai_chain):
        """Test processing when no intent is detected."""
        mock_llm, mock_prompt, mock_parser = mock_openai_chain

        # Mock the chain directly
        mock_chain = Mock()
        mock_chain.invoke = Mock(return_value={
            "intent": None,
            "entities": {}
        })
        mock_prompt.return_value = mock_chain

        nlu = ZeroShotNLUOpenAI()
        # Mock the chain after initialization
        nlu.chain = mock_chain

        message = {"text": "Random text"}

        result = nlu.process(message)

        assert result["intent"]["intent"] is None
        assert result["intent"]["confidence"] == 0.0
        assert "intent_ranking" not in result  # Since intent is None, intent_ranking is not set
