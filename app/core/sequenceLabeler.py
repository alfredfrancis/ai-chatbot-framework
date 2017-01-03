import pycrfsuite
from bson import ObjectId
from nltk import word_tokenize

from app.core import Story
from app.core import posTagger
from featuresExtractor import extractFeatures


def sentToFeatures(sent):
    return [extractFeatures(sent, i) for i in range(len(sent))]


def sentToLabels(sent):
    return [label for token, postag, label in sent]


def sentToTokens(sent):
    return [token for token, postag, label in sent]


def train(storyId):
    story = Story.objects.get(id=ObjectId(storyId))
    labeledSentences = story.labeledSentences

    trainSentences = []
    for item in labeledSentences:
        trainSentences.append(item.data)

    features = [sentToFeatures(s) for s in trainSentences]
    labels = [sentToLabels(s) for s in trainSentences]

    trainer = pycrfsuite.Trainer(verbose=False)
    for xseq, yseq in zip(features, labels):
        trainer.append(xseq, yseq)

    trainer.set_params({
        'c1': 1.0,  # coefficient for L1 penalty
        'c2': 1e-3,  # coefficient for L2 penalty
        'max_iterations': 50,  # stop earlier

        # include transitions that are possible, but not observed
        'feature.possible_transitions': True
    })
    trainer.train('model_files/%s.model' % storyId)
    return True


# Extract Labeles from BIO tagged sentence
def extractEntities(taggedSentence):
    labeled = {}
    labels = set()
    for s, tp in taggedSentence:
        if tp != "O":
            label = tp[2:]
            if tp.startswith("B"):
                labeled[label] = s
                labels.add(label)
            elif tp.startswith("I") and (label in labels):
                labeled[label] += " %s" % s
    return labeled


def extractLabels(predictedLabels):
    labels = []
    for tp in predictedLabels:
        if tp != "O":
            labels.append(tp[2:])
    return labels


def predict(storyId, sentence):
    tokenizedSentence = word_tokenize(sentence)
    taggedToken = posTagger(sentence)
    tagger = pycrfsuite.Tagger()
    tagger.open('model_files/%s.model' % storyId)
    predictedLabels = tagger.tag(sentToFeatures(taggedToken))
    extractedEntities = extractEntities(zip(tokenizedSentence, predictedLabels))
    return extractedEntities