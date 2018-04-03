import pycrfsuite
from nltk import word_tokenize

from flask import current_app as app

from app.core.nlp import posTagger,sentenceTokenize,posTagAndLabel
from app.core.featuresExtractor import extractFeatures


def sentToFeatures(sent):
    return [extractFeatures(sent, i) for i in range(len(sent))]


def sentToLabels(sent):
    return [label for token, postag, label in sent]


def sentToTokens(sent):
    return [token for token, postag, label in sent]


def train(trainSentences,model_name):

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
    labels = []
    for tp in predictedLabels:
        if tp != "O":
            labels.append(tp[2:])
    return labels


def predict(model_name, sentence):
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

        labeled_examples.append(tagged_example)
    print labeled_examples
    return labeled_examples
