from flask import request, jsonify, Response
from ikyWebServer import app

# NLP stuff
from nltk.tag.perceptron import PerceptronTagger
from nltk import word_tokenize
import html2text

import json

# Load and initialize Perceptron tagger
tagger = PerceptronTagger()


def pos_tagger(sentence):
    tokenized_sent = word_tokenize(sentence)
    pos_tagged = tagger.tag(tokenized_sent)
    return pos_tagged


@app.route('/pos_tag', methods=['POST'])
def pos_tag():
    html_text = request.form['text']
    text = html2text.html2text(html_text)
    tagged_token = pos_tagger(text)
    tagged_json = []
    for token, postag in tagged_token:
        tagged_json.append([token, postag, "O"])
    return Response(response=json.dumps(tagged_json, ensure_ascii=False), status=200, mimetype="application/json")


@app.route('/query_tokenize', methods=['POST'])
def query_tokenize():
    print(request.form['text'])
    text = html2text.html2text(request.form['text'])
    token_text = word_tokenize(text)
    plain_token = ""
    for t in token_text:
        plain_token = plain_token + " " + t
    return Response(response=plain_token.strip(), status=200, mimetype="text")


