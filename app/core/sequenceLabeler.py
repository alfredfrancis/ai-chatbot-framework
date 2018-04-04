import pycrfsuite
from nltk import word_tokenize

from flask import current_app as app

from app.core.nlp import posTagger,sentenceTokenize,posTagAndLabel

def extractFeatures(sent, i):
    """
    Extract features for a given sentence
    :param sent:
    :param i:
    :return:
    """
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



def sentToFeatures(sent):
    """
    Extract features from training Data
    :param sent:
    :return:
    """
    return [extractFeatures(sent, i) for i in range(len(sent))]


def sentToLabels(sent):
    """
    Extract labels from training data
    :param sent:
    :return:
    """
    return [label for token, postag, label in sent]


def sentToTokens(sent):
    """
    Extract tokens from training data
    :param sent:
    :return:
    """
    return [token for token, postag, label in sent]


def train(trainSentences,model_name):
    """
    Train NER model for given model
    :param trainSentences:
    :param model_name:
    :return:
    """
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
    trainer.train('model_files/%s.model' % model_name)
    return True


# Extract Labeles from BIO tagged sentence
def extractEntities(taggedSentence):
    """
    Extract label-value pair from NER prediction output
    :param taggedSentence:
    :return:
    """
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
    """
    Extract name of labels from NER
    :param predictedLabels:
    :return:
    """
    labels = []
    for tp in predictedLabels:
        if tp != "O":
            labels.append(tp[2:])
    return labels


def predict(model_name, sentence):
    """
    Predict NER labels for given model and query
    :param model_name:
    :param sentence:
    :return:
    """
    tokenizedSentence = word_tokenize(sentence)
    taggedToken = posTagger(sentence)
    tagger = pycrfsuite.Tagger()
    tagger.open("{}/{}.model".format(app.config["MODELS_DIR"], model_name))
    predictedLabels = tagger.tag(sentToFeatures(taggedToken))
    extractedEntities = extractEntities(
        zip(tokenizedSentence, predictedLabels))
    return extractedEntities


def json2crf(trainingData):
    """
    Takes json annotated data and convert to CRF representation
    :param trainingData:
    :return labeled_examples:
    """
    labeled_examples = []

    for example in trainingData:
        tagged_example = posTagAndLabel(example.get("text"))

        # find no of words before selection
        for enitity in example.get("entities"):
            word_count = 0
            char_count = 0
            for i,item in enumerate(tagged_example):
                char_count += len(item[0])
                if enitity.get("begin") == 0:
                    word_count = 0
                    break
                elif  char_count < enitity.get("begin"):
                    word_count += 1
                else:
                    break

            selection = example.get("text")[enitity.get("begin"):enitity.get("end")]
            tokens = sentenceTokenize(selection).split(" ")
            selection_word_count = len(tokens)

            # build BIO tagging
            for i in range(1, selection_word_count+1):
                if i ==1:
                    bio = "B-" + enitity.get("name")
                else:
                    bio = "I-" + enitity.get("name")
                tagged_example[(word_count + i) - 1][2] = bio
        print(tagged_example)
        labeled_examples.append(tagged_example)
    print labeled_examples
    return labeled_examples
