import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '../../../'))

import pytest
from unittest.mock import Mock, patch
from app.bot.nlu.pipeline import NLUPipeline, NLUComponent


class TestNLUPipeline:
    def test_init_without_components(self):
        """Test NLUPipeline initialization without components."""
        pipeline = NLUPipeline()
        assert pipeline.components == []

    def test_init_with_components(self):
        """Test NLUPipeline initialization with components."""
        component1 = Mock(spec=NLUComponent)
        component2 = Mock(spec=NLUComponent)

        pipeline = NLUPipeline([component1, component2])
        assert len(pipeline.components) == 2
        assert pipeline.components[0] == component1
        assert pipeline.components[1] == component2

    def test_add_component(self):
        """Test adding a component to the pipeline."""
        pipeline = NLUPipeline()
        component = Mock(spec=NLUComponent)

        pipeline.add_component(component)
        assert len(pipeline.components) == 1
        assert pipeline.components[0] == component

    @patch("os.path.exists")
    @patch("os.makedirs")
    def test_train(self, mock_makedirs, mock_exists):
        """Test training all components in the pipeline."""
        mock_exists.return_value = False

        component1 = Mock(spec=NLUComponent)
        component2 = Mock(spec=NLUComponent)

        pipeline = NLUPipeline([component1, component2])
        training_data = [{"text": "Hello", "intent": "greet"}]

        pipeline.train(training_data, "/tmp/model")

        component1.train.assert_called_once_with(training_data, "/tmp/model")
        component2.train.assert_called_once_with(training_data, "/tmp/model")
        mock_makedirs.assert_called_once_with("/tmp/model")

    def test_load_success(self):
        """Test successful loading of all components."""
        component1 = Mock(spec=NLUComponent)
        component1.load.return_value = True
        component2 = Mock(spec=NLUComponent)
        component2.load.return_value = True

        pipeline = NLUPipeline([component1, component2])

        result = pipeline.load("/tmp/model")
        assert result is True

        component1.load.assert_called_once_with("/tmp/model")
        component2.load.assert_called_once_with("/tmp/model")

    def test_load_failure(self):
        """Test loading failure when one component fails."""
        component1 = Mock(spec=NLUComponent)
        component1.load.return_value = True
        component2 = Mock(spec=NLUComponent)
        component2.load.return_value = False

        pipeline = NLUPipeline([component1, component2])

        result = pipeline.load("/tmp/model")
        assert result is False

        component1.load.assert_called_once_with("/tmp/model")
        component2.load.assert_called_once_with("/tmp/model")

    def test_process(self):
        """Test processing message through all components."""
        component1 = Mock(spec=NLUComponent)
        component1.process.return_value = {"text": "Hello", "processed1": True}

        component2 = Mock(spec=NLUComponent)
        component2.process.return_value = {"text": "Hello", "processed1": True, "processed2": True}

        pipeline = NLUPipeline([component1, component2])
        message = {"text": "Hello"}

        result = pipeline.process(message)

        assert result["processed1"] is True
        assert result["processed2"] is True

        # Verify components are called in order
        component1.process.assert_called_once_with(message)
        component2.process.assert_called_once_with({"text": "Hello", "processed1": True})

    def test_process_empty_pipeline(self):
        """Test processing with empty pipeline."""
        pipeline = NLUPipeline()
        message = {"text": "Hello"}

        result = pipeline.process(message)
        assert result == message

    def test_process_single_component(self):
        """Test processing with single component."""
        component = Mock(spec=NLUComponent)
        component.process.return_value = {"text": "Hello", "processed": True}

        pipeline = NLUPipeline([component])
        message = {"text": "Hello"}

        result = pipeline.process(message)

        assert result["processed"] is True
        component.process.assert_called_once_with(message)
