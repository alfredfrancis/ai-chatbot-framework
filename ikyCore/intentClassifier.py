from ikyCore.models import Story
from ikyCommons.validations import isListEmpty

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
        stories = Story.objects

        trainLabels = []
        self.labeledSentences = []
        for story in stories:
            labeledSentencesTemp = story.labeledSentences
            if not isListEmpty(labeledSentencesTemp):
                for labeledSentence in labeledSentencesTemp:
                    self.labeledSentences.append(labeledSentence.data)
                    trainLabels.append([str(story.id)])
            else:
                continue
        self.Y = self.lb.fit_transform(trainLabels)

    def train(self):
        trainFeatures = []
        for labeledSentence in self.labeledSentences:
            lq = ""
            for i, token in enumerate(labeledSentence):
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
        joblib.dump(classifier, 'ikyWareHouse/models/intent.pkl', compress=3)
        return True

    def predict(self, sentence):
        try:
            # Prediction using Model
            classifier = joblib.load('ikyWareHouse/models/intent.pkl')
        except IOError:
            return False

        predicted = classifier.predict([sentence])

        if predicted.any():
            all_labels = self.lb.inverse_transform(predicted)
            return all_labels[0][0]
        else:
            return False
