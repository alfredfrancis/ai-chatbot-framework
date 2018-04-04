
import app.core.SequenceLabeler as SequenceLabeler
from app.stories.models import Story

from app import app
from app.core.intent_classifer import IntentClassifier


def train_models():
    """
    Initiate NER and Intent Classification training
    :return:
    """
    # generate intent classifier training data
    stories = Story.objects

    if not stories:
        raise Exception("NO_DATA")

    # train intent classifier on all stories
    train_intent_classifier(stories)

    # train ner model for each Stories
    for story in stories:
        train_all_ner(str(story.id), story.trainingData)


def train_intent_classifier(stories):
    """
    Train intent classifier model
    :param stories:
    :return:
    """
    X = []
    y = []
    for story in stories:
        training_data = story.trainingData
        for example in training_data:
            X.append(example.get("text"))
            y.append([str(story.id)])

    PATH = "{}/{}".format(app.config["MODELS_DIR"],
                          app.config["INTENT_MODEL_NAME"])

    print(X)
    print(y)
    intent_classifier = IntentClassifier()
    intent_classifier.train(X,
                            y,
                            outpath=PATH, verbose=False)


def train_all_ner(story_id, training_data):
    """
    Train NER model for single Story
    :param story_id:
    :param training_data:
    :return:
    """
    # generate crf training data
    ner_training_data = SequenceLabeler.json2crf(training_data)
    # train and store ner model
    SequenceLabeler.train(ner_training_data, story_id)
