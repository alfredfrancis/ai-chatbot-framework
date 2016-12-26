from core.models import Story
from commons.validations import isListEmpty

import sentenceClassifer

class IntentClassifier(object):
    def __init__(self):
        stories = Story.objects
        if not stories:
            raise Exception("NO_DATA")
        self.trainLabels = []
        self.labeledSentences = []
        self.trainLabels = []
        self.PATH = 'models/intent.model'
        for story in stories:
            labeledSentencesTemp = story.labeledSentences
            if not isListEmpty(labeledSentencesTemp):
                for labeledSentence in labeledSentencesTemp:
                    self.labeledSentences.append(labeledSentence.data)
                    self.trainLabels.append([str(story.id)])
            else:
                continue

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
        sentenceClassifer.train(trainFeatures,
                                self.trainLabels,
                                outpath=self.PATH)
        return True

    def predict(self, sentence):
        predicted = sentenceClassifer.predict(sentence,self.PATH)
        if not predicted:
            return  Story.objects(intentName="fallback").first().id
        else:
            return predicted["class"]
