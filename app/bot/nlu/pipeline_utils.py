import os
from app.admin.intents.store import list_intents
from app.bot.nlu.pipeline import NLUPipeline
from app.bot.nlu.featurizers import SpacyFeaturizer
from app.bot.nlu.intent_classifiers import SklearnIntentClassifier
from app.bot.nlu.entity_extractors import CRFEntityExtractor
from app.bot.nlu.entity_extractors import SynonymReplacer
from app.bot.nlu.llm import ZeroShotNLUOpenAI
from app.admin.entities.store import list_synonyms
from app.admin.bots.store import get_nlu_config
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
    pipeline = await get_pipeline()
    pipeline.train(training_data, models_dir)


async def get_pipeline():
    nlu_config = await get_nlu_config("default")
    if nlu_config.pipeline_type == "traditional":
        return await create_ml_pipeline(**nlu_config.traditional_settings.dict())
    if nlu_config.pipeline_type == "llm":
        return await create_zero_shot_pipeline(**nlu_config.llm_settings.dict())


async def create_ml_pipeline(**kwargs):
    """
    Create a machine learning pipeline
    :return:
    """
    synonyms = await list_synonyms()
    return NLUPipeline(
        [
            SpacyFeaturizer(app_config.SPACY_LANG_MODEL),
            SklearnIntentClassifier(),
            CRFEntityExtractor(),
            SynonymReplacer(synonyms),
        ]
    )


async def create_zero_shot_pipeline(**kwargs):
    """
    Create a zero shot pipeline
    :return:
    """
    intents = await list_intents()
    synonyms = await list_synonyms()

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
                **kwargs,
            ),
            SynonymReplacer(synonyms),
        ]
    )
