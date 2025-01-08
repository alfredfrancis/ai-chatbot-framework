# -*- coding: utf-8 -*-
import os

from app import DialogueManager
from app.intents.models import Intent
from app.nlu.pipeline import NLUPipeline, IntentClassifier, EntityExtractor, SpacyFeaturizer
from app.dialogue_manager.utils import get_synonyms

def train_pipeline(app):
    """
    Initiate NLU pipeline training
    :return:
    """
    models_dir = app.config["MODELS_DIR"]
    spacy_model_name = app.config["SPACY_LANG_MODEL"]

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
        SpacyFeaturizer(spacy_model_name),
        IntentClassifier(),
        EntityExtractor(synonyms)
    ])
    
    # First pass to add spacy docs to training data
    for example in training_data:
        example = pipeline.components[0].process({"text": example["text"]})
        example["spacy_doc"] = example.get("spacy_doc")
    
    pipeline.train(training_data, models_dir)

    # recreate dialogue manager with new data
    app.dialogue_manager = DialogueManager.from_config(app)

    # update dialogue manager with new models
    app.dialogue_manager.update_model(models_dir)