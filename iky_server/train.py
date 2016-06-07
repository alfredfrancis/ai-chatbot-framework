from flask import request
from iky_server import app

import os

import pycrfsuite

from bson.objectid import ObjectId
from mongo import _get_tagged,_retrieve

from intent_classifier import Intent_classifier


# NER support functions for Feature extration
def _word2features(sent, i):
    word = sent[i][0]
    postag = sent[i][1]
    features = [
        'bias',
        'word.lower=' + word.lower(),
        'word[-3:]=' + word[-3:],
        'word[-2:]=' + word[-2:],
        'word.isupper=%s' % word.isupper(),
        'word.istitle=%s' % word.istitle(),
        'word.isdigit=%s' % word.isdigit(),
        'postag=' + postag,
        'postag[:2]=' + postag[:2],
    ]
    if i > 0:
        word1 = sent[i - 1][0]
        postag1 = sent[i - 1][1]
        features.extend([
            '-1:word.lower=' + word1.lower(),
            '-1:word.istitle=%s' % word1.istitle(),
            '-1:word.isupper=%s' % word1.isupper(),
            '-1:postag=' + postag1,
            '-1:postag[:2]=' + postag1[:2],
        ])
    else:
        features.append('BOS')

    if i < len(sent) - 1:
        word1 = sent[i + 1][0]
        postag1 = sent[i + 1][1]
        features.extend([
            '+1:word.lower=' + word1.lower(),
            '+1:word.istitle=%s' % word1.istitle(),
            '+1:word.isupper=%s' % word1.isupper(),
            '+1:postag=' + postag1,
            '+1:postag[:2]=' + postag1[:2],
        ])
    else:
        features.append('EOS')

    return features


def _sent2features(sent):
    return [_word2features(sent, i) for i in range(len(sent))]


def _sent2labels(sent):
    return [label for token, postag, label in sent]


def _sent2tokens(sent):
    return [token for token, postag, label in sent]

# Manual tag text chunks


@app.route('/build_model', methods=['POST'])
def build_model():
    story_id =request.form['story_id']

    train_sents = _get_tagged(query={ "story_id":story_id})

    X_train = [_sent2features(s) for s in train_sents]
    y_train = [_sent2labels(s) for s in train_sents]

    trainer = pycrfsuite.Trainer(verbose=False)
    for xseq, yseq in zip(X_train, y_train):
        trainer.append(xseq, yseq)

    trainer.set_params({
        'c1': 1.0,   # coefficient for L1 penalty
        'c2': 1e-3,  # coefficient for L2 penalty
        'max_iterations': 50,  # stop earlier

        # include transitions that are possible, but not observed
        'feature.possible_transitions': True
    })
    trainer.train('models/%s.model'%story_id)

    Intent_classifier().context_train()
    return "1"       
