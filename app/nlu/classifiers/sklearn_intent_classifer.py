import cloudpickle
from sklearn import preprocessing
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.svm import SVC
from sklearn.pipeline import Pipeline
from app.nlu.nltk_preprocessor import NLTKPreprocessor


class SklearnIntentClassifier():

    def __init__(self):
        self.model = None

    def identity(self, arg):
        """
        Simple identity function works as a passthrough.
        """
        return arg

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
                ('preprocessor', NLTKPreprocessor()),
                ('vectorizer', TfidfVectorizer(
                    tokenizer=self.identity, preprocessor=None, lowercase=False)),
                ('clf', SVC(C=1,
                            probability=True,
                            class_weight='balanced'))])

            from sklearn.model_selection import GridSearchCV

            Cs = [0.01,0.25,1, 2, 5, 10, 20, 100]
            param_grid = {'clf__C': Cs, 'clf__kernel': ["linear"]}
            grid_search = GridSearchCV(model,
                                       param_grid=param_grid,
                                       scoring='f1_weighted',
                                       verbose=1)
            grid_search.fit(X, y)

            model = grid_search
            return model

        print(X)
        print(len(y))

        model = build(X, y)

        if outpath:
            with open(outpath, 'wb') as f:
                cloudpickle.dump(model, f)

                if verbose:
                    print("Model written out to {}".format(outpath))

        return model

    def load(self, PATH):
        try:
            with open(PATH, 'rb') as f:
                self.model = cloudpickle.load(f)
        except IOError:
            return False

    def predict(self, text):
        """
        Predict class label for given model
        :param text:
        :param PATH:
        :return:
        """
        return self.process(text)

    def predict_proba(self, X):
        """Given a bow vector of an input text, predict most probable label. Returns only the most likely label.

        :param X: bow of input text
        :return: tuple of first, the most probable label and second, its probability"""

        import numpy as np

        pred_result = self.model.predict_proba(X)
        print(pred_result)
        # sort the probabilities retrieving the indices of the elements in sorted order
        sorted_indices = np.fliplr(np.argsort(pred_result, axis=1))
        return sorted_indices, pred_result[:, sorted_indices]

    def process(self, x, return_type="intent", INTENT_RANKING_LENGTH=5):
        """Returns the most likely intent and its probability for the input text."""

        if not self.model:
            print("no class")
            intent = None
            intent_ranking = []
        else:
            intents, probabilities = self.predict_proba([x])
            intents, probabilities = [self.model.classes_[intent] for intent in
                                      intents.flatten()], probabilities.flatten()

            if len(intents) > 0 and len(probabilities) > 0:
                ranking = list(zip(list(intents), list(probabilities)))[:INTENT_RANKING_LENGTH]

                intent = {"intent": intents[0], "confidence": probabilities[0]}
                intent_ranking = [{"intent": intent_name, "confidence": score} for intent_name, score in ranking]
            else:
                intent = {"name": None, "confidence": 0.0}
                intent_ranking = []
        if return_type == "intent":
            return intent
        else:
            return intent_ranking
