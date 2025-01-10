# -*- coding: utf-8 -*-
import os

from app.bot.dialogue_manager.dialogue_manager import DialogueManager
from app.admin.intents.store import list_intents
from app.bot.nlu.pipeline import NLUPipeline, IntentClassifier, EntityExtractor, SpacyFeaturizer
from app.bot.dialogue_manager.utils import get_synonyms

from app.config import app_config

async def train_pipeline(app):
    """
    Initiate NLU pipeline training
    :return:
    """
    models_dir = app_config.MODELS_DIR
    spacy_model_name = app_config.SPACY_LANG_MODEL

    if not os.path.exists(models_dir):
        os.makedirs(models_dir)

    # get all intents
    intents = await list_intents()
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
    synonyms = await get_synonyms()
    pipeline = NLUPipeline([
        SpacyFeaturizer(spacy_model_name),
        IntentClassifier(),
        EntityExtractor(synonyms)
    ])

    pipeline.train(training_data, models_dir)

    # recreate dialogue manager with new data
    app.state.dialogue_manager = await DialogueManager.from_config()

    # update dialogue manager with new models
    app.state.dialogue_manager.update_model(models_dir)