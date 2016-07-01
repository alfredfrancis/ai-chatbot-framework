import ast
from time import time

import pycrfsuite
from bson import ObjectId
from nltk import word_tokenize

from ikyCore.functions import dateFromString
from ikyCore.nlp import pos_tagger
from ikyWareHouse.mongo import _retrieve, _insert
from featuresExtractor import extractFeatures

def sentToFeatures(sent):
    return [extractFeatures(sent, i) for i in range(len(sent))]


def sentToLabels(sent):
    return [label for token, postag, label in sent]


def sentToTokens(sent):
    return [token for token, postag, label in sent]

def train(storyId):

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
    trainer.train('ikyWareHouse/models/%s.model' % story_id)

    IntentClassifier().train()
    return "1"


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


def predict(stroyId,query):
    # query = request.args.get('query')
    begin = time()

    query = {"_id": ObjectId(story_id)}
    story = _retrieve("stories", query)
    token_text = word_tokenize(user_say)

    tagged_token = pos_tagger(user_say)
    tagger = pycrfsuite.Tagger()
    tagger.open('ikyWareHouse/models/%s.model' % story_id)
    tagged = tagger.tag(_sent2features(tagged_token))

    labels_original = set(story[0]['labels'])
    labels_predicted = set([x.lower() for x in extract_labels(tagged)])

    tagged_dic = {}
    tagged_dic["intent"] = story[0]['action']
    tagged_dic["action_type"] = story[0]['action_type']
    # if labels_original == labels_predicted:

    if len(labels_original) != 0:
        tagged_dic["labels"] = extract_chunks(zip(token_text, tagged))
        if "date" in tagged_dic["labels"]:
            tagged_dic["labels"]["date"] = dateFromString(tagged_dic["labels"]["date"])

    print("Total time taken :" + str(round(time() - begin, 3)) + "s")
    logs ={
        "user":"1",
        "query":user_say,
        "predicted": tagged_dic["labels"]
    }
    _insert("logs", logs)
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