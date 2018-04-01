
import app.core.sequenceLabeler as sequenceLabeler
from app.stories.models import Story

from app import app
from app.core.sentenceClassifer import SentenceClassifier

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
        train_all_ner(str(story.id),story.trainingData)


def train_intent_classifier(stories):
    """
    Train intent classifier model
    :param stories:
    :return:
    """
    X= []
    y= []
    for story in stories:
        trainingData = story.trainingData
        for example in trainingData:
            X.append(example.get("text"))
            y.append(str(story.id))

    PATH = "{}/{}".format(app.config["MODELS_DIR"],
                                   app.config["INTENT_MODEL_NAME"])

    print(X)
    print(y)
    sentenceClassifer = SentenceClassifier()
    sentenceClassifer.train(X,
                            y,
                            outpath=PATH, verbose=False)


def train_all_ner(storyId,trainingData):
    """
    Train NER model for single Story
    :param storyId:
    :param trainingData:
    :return:
    """
    # generate crf training data
    ner_training_data = sequenceLabeler.json2crf(trainingData)
    # train and store ner model
    sequenceLabeler.train(ner_training_data,storyId)