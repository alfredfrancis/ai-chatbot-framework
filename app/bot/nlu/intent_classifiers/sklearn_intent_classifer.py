import os
from typing import Dict, Any

import cloudpickle
import numpy as np

class SklearnIntentClassifier:

    def __init__(self):
        self.model = None

    def get_spacy_embedding(self, spacy_doc):
        """
        perform basic cleaning,tokenization and lemmatization
        :param sentence:
        :return list of clean tokens:
        """
        return np.array(spacy_doc.vector)

    def train(self, training_data, outpath=None, verbose=True):
        """
        Train intent classifier for given training data
        :param X:
        :param y:
        :param outpath:
        :param verbose:
        :return:
        """
        from sklearn.model_selection import GridSearchCV
        from sklearn.svm import SVC

        X = []
        y = []
        for example in training_data:
            if example.get("text", "").strip() == "":
                continue
            X.append(example.get("spacy_doc"))
            y.append(example.get("intent"))

        X = np.stack(
            [
                self.get_spacy_embedding(example)
                for example in X
            ]
        )

        items, counts = np.unique(y, return_counts=True)
        cv_splits = max(2, min(5, np.min(counts) // 5))

        tuned_parameters = [
            {"C": [1, 2, 5, 10, 20, 100], "gamma": [0.1], "kernel": ["linear"]}
        ]

        classifier = GridSearchCV(
                SVC(C=1, probability=True, class_weight="balanced"),
                param_grid=tuned_parameters,
                n_jobs=-1,
                cv=cv_splits,
                scoring="f1_weighted",
                verbose=1,
            )

        classifier.fit(X, y)

        if outpath:
            path = os.path.join(outpath, "sklearn_intent_model.hd5")
            with open(path, 'wb') as f:
                cloudpickle.dump(classifier.best_estimator_, f)

                if verbose:
                    print("Model written out to {}".format(outpath))

        return classifier.best_estimator_

    def load(self, PATH):
        """
        load trained model from given path
        :param PATH:
        :return:
        """
        try:
            PATH = os.path.join(PATH, "sklearn_intent_model.hd5")
            with open(PATH, 'rb') as f:
                self.model = cloudpickle.load(f)
        except IOError:
            return False

    def predict_proba(self, X):
        """Given a bow vector of an input text, predict most probable label.
         Returns only the most likely label.

        :param X: bow of input text
        :return: tuple of first, the most probable label
        and second, its probability"""

        pred_result = self.model.predict_proba([self.get_spacy_embedding(X.get("spacy_doc"))])
        # sort the probabilities retrieving the indices of the elements
        sorted_indices = np.fliplr(np.argsort(pred_result, axis=1))
        return sorted_indices, pred_result[:, sorted_indices]

    def process(self, x: Dict[str, Any], INTENT_RANKING_LENGTH=5):
        """Returns the most likely intent and
        its probability for the input text."""

        intent = {"name": None, "confidence": 0.0}
        intent_ranking = []

        if self.model:
            intents, probabilities = self.predict_proba(x)
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

        return intent, intent_ranking

