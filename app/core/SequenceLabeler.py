import pycrfsuite
from nltk import word_tokenize

from flask import current_app as app

from app.core.nlp import pos_tagger, sentence_tokenize, pos_tag_and_label


def extract_features(sent, i):
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


def sent_to_features(sent):
    """
    Extract features from training Data
    :param sent:
    :return:
    """
    return [extract_features(sent, i) for i in range(len(sent))]


def sent_to_labels(sent):
    """
    Extract labels from training data
    :param sent:
    :return:
    """
    return [label for token, postag, label in sent]


def sent_to_tokens(sent):
    """
    Extract tokens from training data
    :param sent:
    :return:
    """
    return [token for token, postag, label in sent]


def train(train_sentences, model_name):
    """
    Train NER model for given model
    :param train_sentences:
    :param model_name:
    :return:
    """
    features = [sent_to_features(s) for s in train_sentences]
    labels = [sent_to_labels(s) for s in train_sentences]

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
def extract_entities(tagged_sentence):
    """
    Extract label-value pair from NER prediction output
    :param tagged_sentence:
    :return:
    """
    labeled = {}
    labels = set()
    for s, tp in tagged_sentence:
        if tp != "O":
            label = tp[2:]
            if tp.startswith("B"):
                labeled[label] = s
                labels.add(label)
            elif tp.startswith("I") and (label in labels):
                labeled[label] += " %s" % s
    return labeled


def extract_labels(predicted_labels):
    """
    Extract name of labels from NER
    :param predicted_labels:
    :return:
    """
    labels = []
    for tp in predicted_labels:
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
    tokenized_sentence = word_tokenize(sentence)
    tagged_token = pos_tagger(sentence)
    tagger = pycrfsuite.Tagger()
    tagger.open("{}/{}.model".format(app.config["MODELS_DIR"], model_name))
    predicted_labels = tagger.tag(sent_to_features(tagged_token))
    extracted_entities = extract_entities(
        zip(tokenized_sentence, predicted_labels))
    return extracted_entities


def json2crf(training_data):
    """
    Takes json annotated data and convert to CRF representation
    :param training_data:
    :return labeled_examples:
    """
    labeled_examples = []

    for example in training_data:
        tagged_example = pos_tag_and_label(example.get("text"))

        # find no of words before selection
        for enitity in example.get("entities"):
            word_count = 0
            char_count = 0
            for i, item in enumerate(tagged_example):
                char_count += len(item[0])
                if enitity.get("begin") == 0:
                    word_count = 0
                    break
                elif char_count < enitity.get("begin"):
                    word_count += 1
                else:
                    break

            selection = example.get(
                "text")[enitity.get("begin"):enitity.get("end")]
            tokens = sentence_tokenize(selection).split(" ")
            selection_word_count = len(tokens)

            # build BIO tagging
            for i in range(1, selection_word_count+1):
                if i == 1:
                    bio = "B-" + enitity.get("name")
                else:
                    bio = "I-" + enitity.get("name")
                tagged_example[(word_count + i) - 1][2] = bio
        labeled_examples.append(tagged_example)
    return labeled_examples
