import tensorflow as tf
import spacy
from sklearn.preprocessing import LabelBinarizer
import os
import cloudpickle
import time

import numpy as np
np.random.seed(1)

class TfIntentClassifier():

    def __init__(self):
        self.model = None
        self.nlp = spacy.load('en')
        self.label_encoder = LabelBinarizer()
        self.graph=None

    def train(self, X, y, models_dir=None, verbose=True):
        """
        Train intent classifier for given training data
        :param X:
        :param y:
        :param outpath:
        :param verbose:
        :return:
        """

        def create_model():
            """
            Define and return tensorflow model.
            """
            model = tf.keras.Sequential()
            model.add(tf.keras.layers.Dense(512, activation=tf.nn.relu, input_shape=(vocab_size,)))
            model.add(tf.keras.layers.Dense(256, activation=tf.nn.relu))
            model.add(tf.keras.layers.Dense(num_labels, activation=tf.nn.softmax))

            """
            loss functions tried =>  categorical_crossentropy,binary_crossentropy
            optimizers tried => adam,rmsprop
            """
            
            model.compile(loss='categorical_crossentropy',
                          optimizer='adam',
                          metrics=['accuracy'])

            model.summary()

            return model

        # spacy context vector size
        vocab_size = 384

        # create spacy doc vector matrix
        x_train = np.array([list(self.nlp(x).vector) for x in X])

        num_labels = len(set(y))
        self.label_encoder.fit(y)
        y_train = self.label_encoder.transform(y)

        del self.model
        tf.keras.backend.clear_session()
        time.sleep(3)

        self.model = create_model()
        # start training
        self.model.fit(x_train, y_train, shuffle=True, epochs=50, verbose=1)

        if models_dir:
            tf.keras.models.save_model(
                self.model,
                os.path.join(models_dir, "tf_intent_model.hd5")

            )
            if verbose:
                print("TF Model written out to {}".format(os.path.join(models_dir, "tf_intent_model.hd5")))

            cloudpickle.dump(self.label_encoder, open(os.path.join(models_dir, "labels.pkl"), 'wb'))

            if verbose:
                print("Labels written out to {}".format(os.path.join(models_dir, "labels.pkl")))


    def load(self, models_dir):
        try:
            del self.model
            tf.keras.backend.clear_session()
            self.model = tf.keras.models.load_model(os.path.join(models_dir, "tf_intent_model.hd5"),compile=True)
            self.graph = tf.get_default_graph()
            print("Tf model loaded")
            with open(os.path.join(models_dir, "labels.pkl"), 'rb') as f:
                self.label_encoder = cloudpickle.load(f)
                print("Labels model loaded")

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

    def predict_proba(self, x):
        """Given a bow vector of an input text, predict most probable label. Returns only the most likely label.

        :param x: raw input text
        :return: tuple of first, the most probable label and second, its probability"""

        x_predict = [self.nlp(x).vector]
        with self.graph.as_default():
            pred_result = self.model.predict(np.array([x_predict[0]]))
        sorted_indices = np.fliplr(np.argsort(pred_result, axis=1))
        return sorted_indices, pred_result[:, sorted_indices]

    def process(self, x, return_type="intent", INTENT_RANKING_LENGTH=5):
        """Returns the most likely intent and its probability for the input text."""

        if not self.model:
            print("no class")
            intent = None
            intent_ranking = []
        else:
            intents, probabilities = self.predict_proba(x)
            intents, probabilities = [self.label_encoder.classes_[intent] for intent in
                                      intents.flatten()], probabilities.flatten()

            if len(intents) > 0 and len(probabilities) > 0:
                ranking = list(zip(list(intents), list(probabilities)))[:INTENT_RANKING_LENGTH]

                intent = {"intent": intents[0], "confidence": float("%.2f"%probabilities[0])}
                intent_ranking = [{"intent": intent_name, "confidence": float("%.2f"%score)} for intent_name, score in ranking]
            else:
                intent = {"name": None, "confidence": 0.0}
                intent_ranking = []
        if return_type == "intent":
            return intent
        else:
            return intent_ranking
