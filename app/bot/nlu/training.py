import os

from app.admin.intents.store import list_intents
from app.bot.nlu.pipeline import NLUPipeline
from app.bot.nlu.featurizers import SpacyFeaturizer
from app.bot.nlu.intent_classifiers import SklearnIntentClassifier
from app.bot.nlu.entity_extractors import CRFEntityExtractor
from app.admin.entities.store import list_synonyms
from app.config import app_config


async def train_pipeline():
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
    synonyms = await list_synonyms()
    pipeline = NLUPipeline(
        [
            SpacyFeaturizer(spacy_model_name),
            SklearnIntentClassifier(),
            CRFEntityExtractor(synonyms),
        ]
    )

    pipeline.train(training_data, models_dir)
