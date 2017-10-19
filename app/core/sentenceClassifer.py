import os
import pickle

from sklearn import preprocessing
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.multiclass import OneVsRestClassifier
from sklearn.pipeline import Pipeline
from sklearn.svm import LinearSVC
from app.core.NLTKPreprocessor import NLTKPreprocessor


def identity(arg):
    """
    Simple identity function works as a passthrough.
    """
    return arg


def train(X, y, outpath=None, verbose=True):
    def build(X, y=None):
        """
        Inner build function that builds a single model.
        """
        model = Pipeline([
            ('preprocessor', NLTKPreprocessor()),
            ('vectorizer', TfidfVectorizer(
                tokenizer=identity, preprocessor=None, lowercase=False)),
            ('clf', OneVsRestClassifier(LinearSVC()))])

        model.fit(X, y)
        return model

    # Label encode the targets
    labels = preprocessing.MultiLabelBinarizer()
    y = labels.fit_transform(y)

    model = build(X, y)
    model.labels_ = labels

    if outpath:
        with open(outpath, 'wb') as f:
            pickle.dump(model, f)

            if verbose:
                print("Model written out to {}".format(outpath))

    return model


def predict(text, PATH):
    try:
        with open(PATH, 'rb') as f:
            model = pickle.load(f)
    except IOError:
        return False

    yhat = model.predict([
        text
    ])
    if yhat.any():
        return {
            "class": model.labels_.inverse_transform(yhat)[0][0],
            "accuracy": 1
        }
    else:
        return False
