from core.models import Story
from commons.validations import isListEmpty

import numpy as np
from sklearn import preprocessing
from sklearn.externals import joblib
from sklearn.feature_extraction.text import CountVectorizer
from sklearn.feature_extraction.text import TfidfTransformer
from sklearn.multiclass import OneVsRestClassifier
from sklearn.pipeline import Pipeline
from sklearn.svm import LinearSVC

import sentenceClassifer

class IntentClassifier(object):
    def __init__(self):
        # self.lb = preprocessing.MultiLabelBinarizer()
        stories = Story.objects
        if not stories:
            raise Exception("NO_DATA")
        trainLabels = []
        self.labeledSentences = []
        self.trainLabels = []
        self.PATH = 'models/intent.model'
        for story in stories:
            labeledSentencesTemp = story.labeledSentences
            if not isListEmpty(labeledSentencesTemp):
                for labeledSentence in labeledSentencesTemp:
                    self.labeledSentences.append(labeledSentence.data)
                    trainLabels.append([str(story.id)])
            else:
                continue
        # self.Y = self.lb.fit_transform(trainLabels)

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

        sentenceClassifer.train(self.labeledSentences,
                                self.trainLabels,
                                outpath=self.PATH)

        # self.X = np.array(trainFeatures)
        #
        # classifier = Pipeline([
        #     ('vectorizer', CountVectorizer()),
        #     ('tfidf', TfidfTransformer()),
        #     ('clf', OneVsRestClassifier(LinearSVC(C=0.4)))])
        #
        # classifier.fit(self.X, self.Y)

        # dump generated model to file
        # joblib.dump(classifier, 'models/intent.model', compress=3)
        return True

    def predict(self, sentence):
        # try:
        #     # Prediction using Model
        #     classifier = joblib.load(self.PATH)
        # except IOError:
        #     return False

        predicted = sentenceClassifer.predict(sentence,self.PATH)["class"]
        return predicted
        # if predicted.any():
        #     all_labels = self.lb.inverse_transform(predicted)
        #     return all_labels[0][0]
        # else:
        #     return False
