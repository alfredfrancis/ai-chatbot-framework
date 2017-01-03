from config.development import MODELS_DIR,INTENT_MODEL_NAME,DEFAULT_FALLBACK_INTENT_NAME

import sentenceClassifer
from app.commons import isListEmpty
from app.core import Story


class IntentClassifier():
    def __init__(self):
        self.PATH = "{}/{}".format(MODELS_DIR,INTENT_MODEL_NAME)

    def train(self):
        stories = Story.objects
        if not stories:
            raise Exception("NO_DATA")

        labeledSentences = []
        trainLabels = []

        for story in stories:
            labeledSentencesTemp = story.labeledSentences
            if not isListEmpty(labeledSentencesTemp):
                for labeledSentence in labeledSentencesTemp:
                    labeledSentences.append(labeledSentence.data)
                    trainLabels.append([str(story.id)])
            else:
                continue

        trainFeatures = []
        for labeledSentence in labeledSentences:
            lq = ""
            for i, token in enumerate(labeledSentence):
                if i != 0:
                    lq += " " + token[0]
                else:
                    lq = token[0]
            trainFeatures.append(lq)
        sentenceClassifer.train(trainFeatures,
                                trainLabels,
                                outpath=self.PATH, verbose=False)
        return True

    def predict(self, sentence):
        predicted = sentenceClassifer.predict(sentence, self.PATH)
        if not predicted:
            return  Story.objects(intentName=DEFAULT_FALLBACK_INTENT_NAME).first().id
        else:
            return predicted["class"]
