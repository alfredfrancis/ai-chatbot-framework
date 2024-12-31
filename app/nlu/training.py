# -*- coding: utf-8 -*-
import os

from flask import current_app as app
from app.chat.controllers import dialogue_manager
from app.intents.models import Intent
from app.nlu.classifiers.sklearn_intent_classifer import \
    SklearnIntentClassifier
from app.nlu.entity_extractors.crf_entity_extractor import EntityExtractor

def train_models(app):
    """
    Initiate NER and Intent Classification training
    :return:
    """
    # create models dir if doesnt exist
    if not os.path.exists(app.config["MODELS_DIR"]):
        os.makedirs(app.config["MODELS_DIR"])

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