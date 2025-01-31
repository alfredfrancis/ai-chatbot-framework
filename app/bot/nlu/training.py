import os
from typing import List
from app.admin.intents.store import list_intents
from app.admin.intents.schemas import Intent
from app.bot.nlu.pipeline import NLUPipeline
from app.bot.nlu.featurizers import SpacyFeaturizer
from app.bot.nlu.intent_classifiers import SklearnIntentClassifier
from app.bot.nlu.entity_extractors import CRFEntityExtractor
from app.bot.nlu.llm import ZeroShotNLUOpenAI
from app.admin.entities.store import list_synonyms
from app.config import app_config


async def train_pipeline():
    """
    Initiate NLU pipeline training
    :return:
    """
    models_dir = app_config.MODELS_DIR

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
    pipeline = create_zero_shot_pipeline(intents)
    pipeline.train(training_data, models_dir)


def create_ml_pipeline():
    """
    Create a machine learning pipeline
    :return:
    """
    synonyms = await list_synonyms()
    return NLUPipeline(
        [
            SpacyFeaturizer(app_config.SPACY_LANG_MODEL),
            SklearnIntentClassifier(),
            CRFEntityExtractor(synonyms),
        ]
    )


def create_zero_shot_pipeline(intents: List[Intent]):
    """
    Create a zero shot pipeline
    :return:
    """

    intent_ids = []
    entity_ids = []

    for intent in intents:
        intent_ids.append(intent.intentId)
        for parameter in intent.parameters:
            entity_ids.append(parameter.name)

    return NLUPipeline(
        [
            ZeroShotNLUOpenAI(
                intents=intent_ids,
                entities=entity_ids,
                model_name="llama3:8b-instruct-q4_0",
            )
        ]
    )
