import os
import pickle

from sklearn import preprocessing
from sklearn.feature_extraction.text import CountVectorizer
from sklearn.feature_extraction.text import TfidfTransformer
from sklearn.multiclass import OneVsRestClassifier
from sklearn.pipeline import Pipeline
from sklearn.svm import LinearSVC
from NLTKPreprocessor import NLTKPreprocessor
def train(X, y,outpath=None, verbose=True):
    def build(X, y=None):
        """
        Inner build function that builds a single model.
        """
        model = Pipeline([
            ('preprocessor',NLTKPreprocessor()),
            ('vectorizer', CountVectorizer()),
            ('tfidf', TfidfTransformer()),
            ('clf', OneVsRestClassifier(LinearSVC(C=0.9)))])

        model.fit(X, y)
        return model

    # Label encode the targets
    labels = preprocessing.MultiLabelBinarizer()
    y = labels.fit_transform(y)

    model= build(X, y)
    model.labels_ = labels

    if outpath:
        with open(outpath, 'wb') as f:
            pickle.dump(model, f)

            if verbose:print("Model written out to {}".format(outpath))

    return model

def predict(text,PATH):
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
            "accuracy":1
        }
    else:
        return False


if __name__ == "__main__":
    PATH = "model.pickle"

    if not os.path.exists(PATH):

        X = ["hello",
             "fuck you",
             "hey",
             "hii",
             "how are you ?"]
        y = ["greeting",
             "bad",
             "greeting",
             "greeting",
             "cool"]

        model = train(X, y, outpath=PATH)

    else:
        with open(PATH, 'rb') as f:
            model = pickle.load(f)

    with open(PATH, 'rb') as f:
        model = pickle.load(f)

    yhat = model.predict([
        "sdlfkjdf lkjdlsj dl ksgjdlk"
    ])

    if yhat.any():
        all_labels = model.labels_.inverse_transform(yhat)
        print all_labels[0][0]
        os.remove(PATH)
    else:
        print False
        os.remove(PATH)
    # print(model.labels_.inverse_transform(yhat))