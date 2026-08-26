import pytest
from unittest.mock import Mock, MagicMock, patch
import spacy


@pytest.fixture
def mock_spacy_load():
    with patch("spacy.load") as mock_load:
        mock_nlp = Mock()
        mock_doc = Mock()
        mock_doc.vector = [0.1, 0.2, 0.3]
        mock_nlp.return_value = mock_doc
        mock_load.return_value = mock_nlp
        yield mock_load


@pytest.fixture
def sample_training_data():
    return [
        {"text": "Hello world", "intent": "greet", "spacy_doc": None, "entities": []},
        {"text": "Order pizza", "intent": "order_pizza", "spacy_doc": None, "entities": []},
    ]


@pytest.fixture
def mock_cloudpickle_dump_load():
    with patch("cloudpickle.dump") as mock_dump, patch("cloudpickle.load") as mock_load:
        yield mock_dump, mock_load


@pytest.fixture
def mock_pycrfsuite_tagger():
    with patch("pycrfsuite.Tagger") as mock_tagger:
        yield mock_tagger


@pytest.fixture
def mock_openai_chain():
    with patch("app.bot.nlu.llm.zero_shot_nlu_openai.ChatOpenAI") as mock_llm, \
         patch("app.bot.nlu.llm.zero_shot_nlu_openai.ChatPromptTemplate.from_messages") as mock_prompt, \
         patch("app.bot.nlu.llm.zero_shot_nlu_openai.JsonOutputParser") as mock_parser:
        yield mock_llm, mock_prompt, mock_parser
