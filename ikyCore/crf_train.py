import ast

import pycrfsuite

from intentClassifier import Intent_classifier
#from bson.json_util import loads, dumps
#from bson.objectid import ObjectId

from ikyWareHouse.mongo import _retrieve
from featuresExtractor import extractFeatures

def sentToFeatures(sent):
    return [extractFeatures(sent, i) for i in range(len(sent))]


def sentToLabels(sent):
    return [label for token, postag, label in sent]


def sentToTokens(sent):
    return [token for token, postag, label in sent]

def buildStoryModel(storyId):

    cursor = _retrieve("labled_queries", {"story_id": storyId})

    train_sents = []
    for item in cursor:
        train_sents.append(ast.literal_eval(item["item"].encode('ascii', 'ignore')))

    X_train = [_sent2features(s) for s in train_sents]
    y_train = [_sent2labels(s) for s in train_sents]

    trainer = pycrfsuite.Trainer(verbose=False)
    for xseq, yseq in zip(X_train, y_train):
        trainer.append(xseq, yseq)

    trainer.set_params({
        'c1': 1.0,  # coefficient for L1 penalty
        'c2': 1e-3,  # coefficient for L2 penalty
        'max_iterations': 50,  # stop earlier

        # include transitions that are possible, but not observed
        'feature.possible_transitions': True
    })
    trainer.train('models/%s.model' % story_id)

    Intent_classifier().train()
    return "1"
