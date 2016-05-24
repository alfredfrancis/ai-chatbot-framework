from iky_server import app

from flask import request, jsonify, Response

from itertools import chain

import nltk
import pycrfsuite

import sklearn
from sklearn.metrics import classification_report, confusion_matrix
from sklearn.preprocessing import LabelBinarizer

import json
from bson.objectid import ObjectId
from mongo import _get_tagged,_insert,_retrieve,_delete
import ast

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
    """    train_sents = [
                    [
                    ['send', 'NN', 'O'],
                    ['sms', 'NNS', 'B-TSK'],
                    ['to', 'TO', 'O'],
                    ['8714349616', 'CD', 'B-MOB'],
                    ['saying', 'VBG', 'O'],
                    ['hello', 'NN', 'B-MSG']
                    ],

                    [
                    ['sms', 'NNS', 'B-TSK'], 
                    ['9446623306', 'CD', 'B-MOB'], 
                    ['haai', 'NN', 'B-MSG']
                    ],

                    [
                    ['sms', 'NNS', 'B-TSK'],
                    ['9446623306', 'CD', 'B-MOB'],
                    ['haai', 'NN', 'B-MSG'],
                    ['how', 'WRB', 'I-MSG'],
                    ['are', 'VBP', 'I-MSG'],
                    ['you', 'PRP', 'I-MSG']
                    ]

                    ]
    """
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
    return "1"

       
def extract_chunks(tagged_sent):
    labeled = {}
    labels=[]
    for s, tp in tagged_sent:
        if tp != "O":
            label = tp[2:]
            if tp.startswith("B"):
                labeled[label] = s
            elif tp.startswith("I") and (label not in labels) :
                labels.append(label)
                labeled[label] = s
            elif (tp.startswith("I") and (label in labels)):
                labeled[label] += " %s"%s
    return labeled

@app.route('/predict', methods=['GET'])
def predict(user_say):
    #query = request.args.get('query')
    query= {"user_id":"1"}
    stories = ast.literal_eval(_retrieve("stories",query))
    for story in stories:
        print(story)
        token_text = nltk.word_tokenize(user_say)
        tagged_token = nltk.pos_tag(token_text)
        tagger = pycrfsuite.Tagger()
        tagger.open('models/%s.model'%story['_id']['$oid'])
        tagged = tagger.tag(_sent2features(tagged_token))
        if set(story.labels) == set(y)
            tagged_json= extract_chunks(zip(token_text,tagged))
            return Response(response=json.dumps(tagged_json, ensure_ascii=False), status=200, mimetype="application/json")
    return "Sorry"

@app.route('/pos_tag', methods=['POST'])
def pos_tag():
    text = request.form['text']
    token_text = nltk.word_tokenize(text)
    tagged_token = nltk.pos_tag(token_text)
    tagged_json = []
    for token, postag in tagged_token:
        tagged_json.append([token, postag, "O"])
    return Response(response=json.dumps(tagged_json, ensure_ascii=False), status=200, mimetype="application/json")


@app.route('/query_tokenize', methods=['POST'])
def query_tokenize():
    text = request.form['text']
    token_text = nltk.word_tokenize(text)
    plain_token = ""
    for t in token_text:
        plain_token = plain_token + " " + t
    return Response(response=plain_token.strip(), status=200, mimetype="text")

@app.route('/create_story', methods=['POST'])
def create_story():
    data={
    "user_id" : request.form['user_id'],
    "labels": request.form['labels'].split(","),
    "action":request.form['action_name'],
    "story_name" : request.form['story_name'],
    }
    return _insert("stories",data)

@app.route('/get_stories', methods=['POST'])
def get_stories():
    query= { "user_id":"1"}
    return _retrieve("stories",query)

@app.route('/delete_story', methods=['POST'])
def delete_story():
    query= { "_id":ObjectId(request.form['story_id'])}
    _delete("stories",query);
    query= { "story_id":ObjectId(request.form['story_id'])}
    _delete("labled_queries",query);
    return "1"