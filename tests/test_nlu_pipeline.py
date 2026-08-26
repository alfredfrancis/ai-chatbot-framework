import pytest
from unittest.mock import MagicMock, patch
from app.bot.nlu.featurizers.spacy_featurizer import SpacyFeaturizer
from app.bot.nlu.intent_classifiers.sklearn_intent_classifer import SklearnIntentClassifier
from app.bot.nlu.intent_classifiers.tf_intent_classifer import TfIntentClassifier
from app.bot.nlu.entity_extractors.crf_entity_extractor import CRFEntityExtractor
from app.bot.nlu.entity_extractors.synonym_replacer import SynonymReplacer
from app.bot.nlu.llm.zero_shot_nlu_openai import ZeroShotNLUOpenAI

@pytest.fixture
def sample_text():
    return "Order a large pepperoni pizza"

@pytest.fixture
def spacy_model():
    import spacy
    return spacy.blank("en")

@pytest.fixture
def spacy_featurizer(spacy_model):
    return SpacyFeaturizer(model_name="en")


def test_spacy_featurizer_process(spacy_featurizer, sample_text):
    message = {"text": sample_text}
    result = spacy_featurizer.process(message)
    assert "spacy_doc" in result
    assert result["spacy_doc"].text == sample_text


def test_sklearn_intent_classifier_process():
    clf = SklearnIntentClassifier()
    clf.model = MagicMock()
    clf.model.classes_ = ["order_pizza", "greet"]
    clf.model.predict_proba.return_value = [[0.8, 0.2]]
    message = {"text": "Order pizza", "spacy_doc": MagicMock(vector=[1.0, 2.0])}
    result = clf.process(message)
    assert "intent" in result
    assert "intent_ranking" in result


def test_tf_intent_classifier_process():
    clf = TfIntentClassifier()
    clf.model = MagicMock()
    clf.label_encoder = MagicMock()
    clf.label_encoder.classes_ = ["order_pizza", "greet"]
    clf.graph = MagicMock()
    clf.model.predict.return_value = [[0.7, 0.3]]
    message = {"text": "Order pizza"}
    with patch.object(clf, "nlp", MagicMock()):
        result = clf.process(message)
    assert "intent" in result
    assert "intent_ranking" in result


def test_crf_entity_extractor_process():
    extractor = CRFEntityExtractor()
    extractor.tagger = MagicMock()
    extractor.tagger.tag.return_value = ["B-pizza_size", "O", "B-pizza_topping"]
    message = {"text": "large pepperoni", "spacy_doc": MagicMock()}
    with patch.object(extractor, "pos_tagger", return_value=[("large", "JJ"), ("pepperoni", "NN")]):
        with patch.object(extractor, "sent_to_features", return_value=[["feature1"], ["feature2"]]):
            result = extractor.process(message)
    assert "entities" in result


def test_synonym_replacer_process():
    synonyms = {"big": "large"}
    replacer = SynonymReplacer(synonyms=synonyms)
    message = {"entities": {"pizza_size": "big"}}
    result = replacer.process(message)
    assert result["entities"]["pizza_size"] == "large"


def test_zero_shot_nlu_openai_process():
    zsnlu = ZeroShotNLUOpenAI(intents=["order_pizza"], entities=["pizza_size"])
    zsnlu.chain = MagicMock()
    zsnlu.chain.invoke.return_value = {"intent": "order_pizza", "entities": {"pizza_size": "large"}}
    message = {"text": "I want a large pizza"}
    result = zsnlu.process(message)
    assert result["intent"]["intent"] == "order_pizza"
    assert result["entities"]["pizza_size"] == "large" 