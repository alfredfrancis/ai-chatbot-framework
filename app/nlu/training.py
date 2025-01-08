# -*- coding: utf-8 -*-
import os
from app.chat.controllers import dialogue_manager
from app.intents.models import Intent
from app.nlu.pipeline import NLUPipeline, IntentClassifier, EntityExtractor
from app.chat.utils import get_synonyms

def train_pipeline(models_dir):
    """
    Initiate NLU pipeline training
    :return:
    """
    if not os.path.exists(models_dir):
        os.makedirs(models_dir)

    # get all intents
    intents = Intent.objects
    if not intents:
        raise Exception("No intents found for training")

    # prepare training data
    training_data = []
    for intent in intents:
        for example in intent.trainingData:
            if example.get("text").strip() == "":
                continue
            example["intent"] = intent.intentId
            training_data.append(example)

    # initialize and train pipeline
    synonyms = get_synonyms()
    pipeline = NLUPipeline([
        IntentClassifier(),
        EntityExtractor(synonyms)
    ])
    pipeline.train(training_data, models_dir)

    # update dialogue manager with new models
    dialogue_manager.update_model(models_dir)