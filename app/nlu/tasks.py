# -*- coding: utf-8 -*-

from flask import current_app as app
from app.chat.controllers import dialogue_manager
from app.intents.models import Intent
from app import spacy_tokenizer
from app.nlu.classifiers.sklearn_intent_classifer import \
    SklearnIntentClassifier
from app.nlu.entity_extractor import EntityExtractor

def train_models(app):
    """
    Initiate NER and Intent Classification training
    :return:
    """
    # generate intent classifier training data
    intents = Intent.objects

    if not intents:
        raise Exception("NO_DATA")

    # train intent classifier on all intents
    train_intent_classifier(intents)

    # train ner model for each Stories
    for intent in intents:
        train_all_ner(intent.intentId, intent.trainingData)

    dialogue_manager.update_model(app)

def train_intent_classifier(intents):
    """
    Train intent classifier model
    :param intents:
    :return:
    """
    X = []
    y = []
    for intent in intents:
        training_data = intent.trainingData
        for example in training_data:
            if example.get("text").strip() == "":
                continue
            X.append(example.get("text"))
            y.append(intent.intentId)

    intent_classifier = SklearnIntentClassifier()
    intent_classifier.train(X, y,outpath=app.config["MODELS_DIR"])

def train_all_ner(story_id, training_data):
    """
    Train NER model for single Story
    :param story_id:
    :param training_data:
    :return:
    """
    entityExtraction = EntityExtractor()
    # generate crf training data
    ner_training_data = entityExtraction.json2crf(training_data)
    # train and store ner model
    entityExtraction.train(ner_training_data, story_id)


# Load and initialize Perceptron tagger

def pos_tagger(sentence):
    """
    perform POS tagging on a given sentence
    :param sentence:
    :return:
    """
    doc = spacy_tokenizer(sentence)
    taged_sentance = []
    for token in doc:
        taged_sentance.append((token.text, token.tag_))
    return taged_sentance


def pos_tag_and_label(sentence):
    """
    Perform POS tagging and BIO labeling on given sentence
    :param sentence:
    :return:
    """
    tagged_sentence = pos_tagger(sentence)
    tagged_sentence_json = []
    for token, postag in tagged_sentence:
        tagged_sentence_json.append([token, postag, "O"])
    return tagged_sentence_json


def sentence_tokenize(sentences):
    """
    Sentence tokenizer
    :param sentences:
    :return:
    """
    doc = spacy_tokenizer(sentences)
    words = [token.text for token in doc]
    return " ".join(words)
