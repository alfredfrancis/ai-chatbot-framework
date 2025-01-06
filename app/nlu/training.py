import os
from app.database import find_many
from app.nlu.classifiers.sklearn_intent_classifer import SklearnIntentClassifier
from app.nlu.entity_extractors.crf_entity_extractor import EntityExtractor
from app.main import app

async def train_models():
    """
    Initiate NER and Intent Classification training
    """
    # create models dir if doesnt exist
    if not os.path.exists(app.state.config["MODELS_DIR"]):
        os.makedirs(app.state.config["MODELS_DIR"])

    # generate intent classifier training data
    intents = await find_many("intents", {})

    if not intents:
        raise Exception("NO_DATA")

    # train intent classifier on all intents
    await train_intent_classifier(intents)

    # train ner model for each Stories
    for intent in intents:
        await train_all_ner(intent["intentId"], intent["trainingData"])

    # Update dialogue manager models
    if hasattr(app.state, "dialogue_manager"):
        await app.state.dialogue_manager.update_model(app)

async def train_intent_classifier(intents):
    """
    Train intent classifier model
    :param intents: List of intent documents
    """
    X = []
    y = []
    for intent in intents:
        training_data = intent["trainingData"]
        for example in training_data:
            if example.get("text", "").strip() == "":
                continue
            X.append(example.get("text"))
            y.append(intent["intentId"])

    intent_classifier = SklearnIntentClassifier()
    intent_classifier.train(X, y, outpath=app.state.config["MODELS_DIR"])

async def train_all_ner(story_id, training_data):
    """
    Train NER model for single Story
    :param story_id: ID of the story/intent
    :param training_data: Training data for NER
    """
    entityExtraction = EntityExtractor()
    # generate crf training data
    ner_training_data = entityExtraction.json2crf(training_data)
    # train and store ner model
    entityExtraction.train(ner_training_data, story_id)