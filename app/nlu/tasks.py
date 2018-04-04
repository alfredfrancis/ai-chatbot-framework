
from app.nlu.entity_extractor import EntityExtractor
from app.stories.models import Story

from app import app
from app.nlu.intent_classifer import IntentClassifier


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
    entityExtraction = EntityExtractor()
    # generate crf training data
    ner_training_data = entityExtraction.json2crf(training_data)
    # train and store ner model
    entityExtraction.train(ner_training_data, story_id)


from nltk.tag.perceptron import PerceptronTagger
from nltk import word_tokenize

# Load and initialize Perceptron tagger
tagger = PerceptronTagger()


def pos_tagger(sentence):
    """
    perform POS tagging on a given sentence
    :param sentence:
    :return:
    """
    tokenized_sentence = word_tokenize(sentence)
    pos_tagged_sentence = tagger.tag(tokenized_sentence)
    return pos_tagged_sentence


def pos_tag_and_label(sentence):
    """
    Perform POS tagging and BIO labeling on given sentence
    :param sentence:
    :return:
    """
    tagged_sentence = pos_tagger(sentence)
    tagged_sentence_json = []
    for token, postag in tagged_sentence:
        tagged_sentence_json.append([token, postag, "O"])
    return tagged_sentence_json


def sentence_tokenize(sentences):
    """
    Sentence tokenizer
    :param sentences:
    :return:
    """
    tokenized_sentences = word_tokenize(sentences)
    return " ".join(tokenized_sentences)
