import ikyWareHouse.mongo

from bson.json_util import loads

import numpy as np
from sklearn import preprocessing
from sklearn.externals import joblib
from sklearn.feature_extraction.text import CountVectorizer
from sklearn.feature_extraction.text import TfidfTransformer
from sklearn.multiclass import OneVsRestClassifier
from sklearn.pipeline import Pipeline
from sklearn.svm import LinearSVC


class IntentClassifier(object):
    def __init__(self):
        self.lb = preprocessing.MultiLabelBinarizer()
        self.labeledStories = ikyWareHouse.mongo._retrieve("labled_queries", {"user_id": "1"})

        trainLabels = []

        for story in self.labeledStories:
            trainLabels.append([story['story_id']])

        self.Y = self.lb.fit_transform(trainLabels)

    def train(self):
        trainFeatures = []

        for story in self.labeledStories:
            lq = ""
            for i, token in enumerate(loads(story["item"])):
                if i != 0:
                    lq += " " + token[0]
                else:
                    lq = token[0]
            trainFeatures.append(lq)

        self.X = np.array(trainFeatures)

        classifier = Pipeline([
            ('vectorizer', CountVectorizer()),
            ('tfidf', TfidfTransformer()),
            ('clf', OneVsRestClassifier(LinearSVC(C=0.4)))])

        classifier.fit(self.X, self.Y)

        # dump generated model to file
        joblib.dump(classifier, 'models/intent.pkl', compress=3)
        return True

    def predict(self, user_say):
        try:
            # Prediction using Model
            classifier = joblib.load('models/intent.pkl')
        except IOError:
            return False

        predicted = classifier.predict([user_say])

        if predicted.any():
            all_labels = self.lb.inverse_transform(predicted)
            return all_labels[0][0]
        else:
            return False
