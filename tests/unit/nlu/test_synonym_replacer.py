import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '../../../'))

import pytest
from app.bot.nlu.entity_extractors.synonym_replacer import SynonymReplacer


class TestSynonymReplacer:
    def test_init_with_synonyms(self):
        """Test SynonymReplacer initialization with synonyms."""
        synonyms = {"hi": "hello", "bye": "goodbye"}
        replacer = SynonymReplacer(synonyms)
        assert replacer.synonyms == synonyms

    def test_init_without_synonyms(self):
        """Test SynonymReplacer initialization without synonyms."""
        replacer = SynonymReplacer()
        assert replacer.synonyms == {}

    def test_replace_synonyms_with_matches(self):
        """Test synonym replacement with matching entities."""
        synonyms = {"ny": "new york", "la": "los angeles"}
        replacer = SynonymReplacer(synonyms)

        entities = {"location": "ny", "destination": "la"}
        result = replacer.replace_synonyms(entities)

        assert result["location"] == "new york"
        assert result["destination"] == "los angeles"

    def test_replace_synonyms_without_matches(self):
        """Test synonym replacement without matching entities."""
        synonyms = {"ny": "new york", "la": "los angeles"}
        replacer = SynonymReplacer(synonyms)

        entities = {"location": "boston", "destination": "chicago"}
        result = replacer.replace_synonyms(entities)

        assert result["location"] == "boston"
        assert result["destination"] == "chicago"

    def test_replace_synonyms_mixed(self):
        """Test synonym replacement with mixed matching and non-matching."""
        synonyms = {"ny": "new york"}
        replacer = SynonymReplacer(synonyms)

        entities = {"location": "ny", "destination": "boston"}
        result = replacer.replace_synonyms(entities)

        assert result["location"] == "new york"
        assert result["destination"] == "boston"

    def test_replace_synonyms_case_insensitive(self):
        """Test synonym replacement is case insensitive."""
        synonyms = {"ny": "new york"}
        replacer = SynonymReplacer(synonyms)

        entities = {"location": "ny"}
        result = replacer.replace_synonyms(entities)

        assert result["location"] == "new york"

    def test_train(self):
        """Test train method (should do nothing)."""
        replacer = SynonymReplacer()
        # Should not raise any exception
        replacer.train({}, "/tmp/model")

    def test_load(self):
        """Test load method."""
        replacer = SynonymReplacer()
        result = replacer.load("/tmp/model")
        assert result is True

    def test_process_with_entities(self):
        """Test processing message with entities."""
        synonyms = {"ny": "new york"}
        replacer = SynonymReplacer(synonyms)

        message = {"text": "I live in ny", "entities": {"location": "ny"}}
        result = replacer.process(message)

        assert result["entities"]["location"] == "new york"
        assert result["text"] == "I live in ny"

    def test_process_without_entities(self):
        """Test processing message without entities."""
        replacer = SynonymReplacer()
        message = {"text": "Hello world"}

        result = replacer.process(message)
        assert result == message

    def test_process_with_empty_entities(self):
        """Test processing message with empty entities."""
        replacer = SynonymReplacer()
        message = {"text": "Hello world", "entities": {}}

        result = replacer.process(message)
        assert result == message
