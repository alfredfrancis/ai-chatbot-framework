import string

import cloudpickle
import numpy as np
import spacy
from nltk.corpus import stopwords
from sklearn.feature_extraction.stop_words import ENGLISH_STOP_WORDS
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.model_selection import GridSearchCV
from sklearn.pipeline import Pipeline
from sklearn.svm import SVC


class SklearnIntentClassifier:

    def __init__(self):

        self.model = None

        self.spacynlp = spacy.load('en')

        self.stopwords = set(stopwords.words('english') +
                             ["n't", "'s", "'m", "ca"] +
                             list(ENGLISH_STOP_WORDS))

        self.punctuations = " ".join(string.punctuation).split(" ") + \
                            ["-----", "---", "...", "'ve"]

    def spacy_tokenizer(self, sentence):
        """
        perform basic cleaning,tokenization and lemmatization
        :param sentence:
        :return list of clean tokens:
        """
        tokens = self.spacynlp(sentence)

        tokens = [tok.lemma_.lower().strip() if
                  tok.lemma_ != "-PRON-" else tok.lower_ for tok in tokens]

        tokens = [tok for tok in tokens if
                  (tok not in self.stopwords and tok not in self.punctuations)]

        while "" in tokens:
            tokens.remove("")
        while " " in tokens:
            tokens.remove(" ")
        while "\n" in tokens:
            tokens.remove("\n")
        while "\n\n" in tokens:
            tokens.remove("\n\n")
        return tokens

    def train(self, X, y, outpath=None, verbose=True):
        """
        Train intent classifier for given training data
        :param X:
        :param y:
        :param outpath:
        :param verbose:
        :return:
        """

        def build(X, y=None):
            """
            Inner build function that builds a single model.
            :param X:
            :param y:
            :return:
            """
            model = Pipeline([
                ('vectorizer', TfidfVectorizer(
                    tokenizer=self.spacy_tokenizer,
                    preprocessor=None, lowercase=False)
                 ),

                ('clf', SVC(C=1, kernel="linear",
                            probability=True, class_weight='balanced')
                 )])

            items, counts = np.unique(y, return_counts=True)

            cv_splits = max(2, min(5, np.min(counts) // 5))

            Cs = [0.01, 0.25, 1, 2, 5, 10, 20, 100]
            param_grid = {'clf__C': Cs, 'clf__kernel': ["linear"]}
            grid_search = GridSearchCV(model,
                                       param_grid=param_grid,
                                       scoring='f1_weighted',
                                       cv=cv_splits,
                                       verbose=2,
                                       n_jobs=-1
                                       )
            grid_search.fit(X, y)

            return grid_search

        model = build(X, y)

        if outpath:
            with open(outpath, 'wb') as f:
                cloudpickle.dump(model, f)

                if verbose:
                    print("Model written out to {}".format(outpath))

        return model

    def load(self, PATH):
        """
        load trained model from given path
        :param PATH:
        :return:
        """
        try:
            with open(PATH, 'rb') as f:
                self.model = cloudpickle.load(f)
        except IOError:
            return False

    def predict(self, text, return_all=False, INTENT_RANKING_LENGTH=5):
        """
        Predict class label for given model
        """
        return self.process(text, return_all, INTENT_RANKING_LENGTH)

    def predict_proba(self, X):
        """Given a bow vector of an input text, predict most probable label.
         Returns only the most likely label.

        :param X: bow of input text
        :return: tuple of first, the most probable label
        and second, its probability"""

        pred_result = self.model.predict_proba(X)
        print(pred_result)
        # sort the probabilities retrieving the indices of the elements
        sorted_indices = np.fliplr(np.argsort(pred_result, axis=1))
        return sorted_indices, pred_result[:, sorted_indices]

    def process(self, x, return_all=False, INTENT_RANKING_LENGTH=5):
        """Returns the most likely intent and
        its probability for the input text."""

        if not self.model:
            print("no class")
            intent = None
            intent_ranking = []
        else:
            intents, probabilities = self.predict_proba([x])
            intents = [self.model.classes_[intent]
                       for intent in intents.flatten()]
            probabilities = probabilities.flatten()

            if len(intents) > 0 and len(probabilities) > 0:
                ranking = list(zip(list(intents), list(probabilities)))
                ranking = ranking[:INTENT_RANKING_LENGTH]

                intent = {"intent": intents[0], "confidence": probabilities[0]}
                intent_ranking = [{"intent": intent_name, "confidence": score}
                                  for intent_name, score in ranking]

            else:
                intent = {"name": None, "confidence": 0.0}
                intent_ranking = []

        if return_all:
            return intent_ranking
        else:
            return intent
