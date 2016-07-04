import pycrfsuite
from bson import ObjectId
from nltk import word_tokenize

from ikyCore.nlp import posTagger
from ikyCore.intentClassifier import IntentClassifier
from ikyCore.models import Story
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
        trainSentences.append(item["data"])

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
    trainer.train('ikyWareHouse/models/%s.model' % storyId)

    IntentClassifier().train()
    return "1"


def extractEntities(taggedSentences):
    labeled = {}
    labels = set()
    for s, tp in taggedSentences:
        if tp != "O":
            label = tp[2:].lower()
            if tp.startswith("B"):
                labeled[label] = s
                labels.add(label)
            elif tp.startswith("I") and (label in labels):
                labeled[label] += " %s" % s
    return labeled


def extractLabels(tagged):
    labels = []
    for tp in tagged:
        if tp != "O":
            labels.append(tp[2:])
    return labels


def predict(storyId,sentence):
    tokenizedSentence = word_tokenize(sentence)
    taggedToken = posTagger(sentence)
    tagger = pycrfsuite.Tagger()
    tagger.open('ikyWareHouse/models/%s.model' % storyId)
    predictedLabels = tagger.tag(sentToFeatures(taggedToken))
    labelsPredicted = set([x.lower() for x in extractLabels(predictedLabels)])
    extractedEntities = extractEntities(zip(tokenizedSentence, labelsPredicted))
    return extractedEntities



    """
    result = {}
    result["intent"] = story['actionName']
    result["action_type"] = story['actionType']
    # if labels_original == labels_predicted:

    if len(labelsOriginal) != 0:
        result["labels"] = extractEntities(zip(tokenizedSentence, labelsPredicted))
        if "date" in result["labels"]:
            result["labels"]["date"] = dateFromString(result["labels"]["date"])

    print("Total time taken :" + str(round(time() - begin, 3)) + "s")

    logs ={
        "user":"1",
        "query":user_say,
        "predicted": result["labels"]
    }
    _insert("logs", logs)
    return result

    # result = execute_action(story[0]['action_type'],story[0]['action'],tagged_json)
    # return result

    # return Response(response=json.dumps(tagged_json, ensure_ascii=False), status=200, mimetype="application/json")
    # elif len(labels_original) == 0:
    # result = execute_action(story[0]['action_type'],story[0]['action'],{})
    # return result
    else:
        tagged_json = {"error" : "%s reqires following details: %s"%(story[0]['story_name'],",".join(story[0]['labels'])) }
        return tagged_json
    """