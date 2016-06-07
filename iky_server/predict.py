from flask import request, jsonify, Response
from iky_server import app

import os

# Iky's tools
from interface import execute_action
from intent_classifier import Intent_classifier
from functions import datefromstring

# NLP stuff
import nltk
import pycrfsuite
from train import _sent2features

# DB stuff
import json
from bson.objectid import ObjectId
from mongo import _retrieve
import ast


# Extract Labeles from BIO tagged sentence
def extract_chunks(tagged_sent):
    labeled = {}
    labels=set()
    for s, tp in tagged_sent:
        if tp != "O":
            label = tp[2:].lower()
            if tp.startswith("B"):
                labeled[label] = s
                labels.add(label)
            elif tp.startswith("I") and (label in labels) :
                labeled[label] += " %s"%s
    return labeled

def extract_labels(tagged):
    labels=[]
    for tp in tagged:
        if tp != "O":
            labels.append(tp[2:])
    return labels

@app.route('/predict', methods=['GET'])
def predict(user_say):
    #query = request.args.get('query')

    story_id = Intent_classifier().context_check(user_say)
    if not story_id:
        return "Sorry,I'm not trained to handle that context."

    query= {"_id":ObjectId(story_id)}
    story = ast.literal_eval(_retrieve("stories",query))

    token_text = nltk.word_tokenize(user_say)
    tagged_token = nltk.pos_tag(token_text)

    tagger = pycrfsuite.Tagger()
    tagger.open('models/%s.model'%story_id)
    tagged = tagger.tag(_sent2features(tagged_token))
    
    labels_original=set(story[0]['labels'])
    labels_predicted=set([x.lower() for x in extract_labels(tagged)])

    if labels_original == labels_predicted:
        tagged_json= extract_chunks(zip(token_text,tagged))
      
        if "date" in tagged_json:
            tagged_json["date"] = datefromstring(tagged_json["date"])
        
        result = execute_action(story[0]['action_type'],story[0]['action'],tagged_json)
        return result
        
        #return Response(response=json.dumps(tagged_json, ensure_ascii=False), status=200, mimetype="application/json")
    elif not len(labels_predicted):
        result = execute_action(story[0]['action_type'],story[0]['action'],{})
        return result    
    else:
        return "%s reqires following details: %s"%(story[0]['story_name'],",".join(story[0]['labels']))

