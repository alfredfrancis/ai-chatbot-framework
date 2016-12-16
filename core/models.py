from mongoengine import *
from config import *
from bson.objectid import ObjectId

connect(IKY_DB)


class LabeledSentences(EmbeddedDocument):
    id = ObjectIdField(required=True, default=lambda: ObjectId())
    data = ListField(required=True)


class Story(Document):
    ACTIONTYPE = (('1', 'Function'),
                  ('2', 'SQL query'),
                  ('3', 'REST API'),
                  ('4', 'Custom Message'))
    storyName = StringField(max_length=100, required=True, unique=True)
    labels = ListField(StringField())
    actionType = StringField(choices=ACTIONTYPE, required=True)
    actionName = StringField(required=True)
    labeledSentences = EmbeddedDocumentListField(LabeledSentences)


if __name__ == '__main__':

    newStory = Story()
    newStory.storyName = 'test'
    newStory.labels = ['']
    newStory.actionName = 'Test Ok'
    newStory.actionType = '1'
    newStory.save()

    newLabeledSentence = LabeledSentences()
    newLabeledSentence.data = [['Test', 'VB', 'O']]
    newStory.labeledSentences.append(newLabeledSentence)
    newStory.save()
