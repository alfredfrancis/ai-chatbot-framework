from flask import request, jsonify, Response
from iky_server import app

# NLP stuff
import nltk

import json

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
