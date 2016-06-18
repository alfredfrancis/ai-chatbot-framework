from flask import request, jsonify, Response
from iky_server import app

from time import time

import os

# Iky's tools
from interface import execute_action
from intent_classifier import Intent_classifier
from functions import datefromstring

# NLP stuff
from nlp import pos_tagger
from nltk import word_tokenize
import pycrfsuite
from crf_train import _sent2features

# DB stuff
from bson.json_util import loads, dumps
from bson.objectid import ObjectId
from mongo import _retrieve
import ast


# Extract Labeles from BIO tagged sentence
def extract_chunks(tagged_sent):
    labeled = {}
    labels = set()
    for s, tp in tagged_sent:
        if tp != "O":
            label = tp[2:].lower()
            if tp.startswith("B"):
                labeled[label] = s
                labels.add(label)
            elif tp.startswith("I") and (label in labels):
                labeled[label] += " %s" % s
    return labeled


def extract_labels(tagged):
    labels = []
    for tp in tagged:
        if tp != "O":
            labels.append(tp[2:])
    return labels


@app.route('/predict', methods=['GET'])
def predict(user_say):
    # query = request.args.get('query')
    begin = time()
    t0 = time()
    story_id = Intent_classifier().context_check(user_say)
    print("Time taken for Intent Classification :" + str(round(time() - t0, 3)) + "s")

    if not story_id:
        return {"error_code": "0", "error_msg": "can't identify the intent"}

    t0 = time()
    query = {"_id": ObjectId(story_id)}
    story = _retrieve("stories", query)
    print("Time taken for Database query :" + str(round(time() - t0, 3)) + "s")

    token_text = word_tokenize(user_say)

    t0 = time()
    tagged_token = pos_tagger(user_say)
    print("Time taken for POS taging :" + str(round(time() - t0, 3)) + "s")

    t0 = time()
    tagger = pycrfsuite.Tagger()
    tagger.open('models/%s.model' % story_id)
    tagged = tagger.tag(_sent2features(tagged_token))
    print("Time taken for Tagging :" + str(round(time() - t0, 3)) + "s")

    labels_original = set(story[0]['labels'])
    labels_predicted = set([x.lower() for x in extract_labels(tagged)])

    tagged_dic = {}
    tagged_dic["intent"] = story[0]['action']
    tagged_dic["action_type"] = story[0]['action_type']
    # if labels_original == labels_predicted:

    t0 = time()
    if len(labels_original) != 0:
        tagged_dic["labels"] = extract_chunks(zip(token_text, tagged))
        if "date" in tagged_dic["labels"]:
            tagged_dic["labels"]["date"] = datefromstring(tagged_dic["labels"]["date"])
    print("Time taken for extracting chunk :" + str(round(time() - t0, 3)) + "s")
    print("Total time taken :" + str(round(time() - begin, 3)) + "s")
    return tagged_dic

    # result = execute_action(story[0]['action_type'],story[0]['action'],tagged_json)
    # return result

    # return Response(response=json.dumps(tagged_json, ensure_ascii=False), status=200, mimetype="application/json")
    # elif len(labels_original) == 0:
    # result = execute_action(story[0]['action_type'],story[0]['action'],{})
    # return result
    """
    else:
        tagged_json = {"error" : "%s reqires following details: %s"%(story[0]['story_name'],",".join(story[0]['labels'])) }
        return tagged_json
    """
