from mongoengine import *
from config import *
from bson.objectid import ObjectId

connect(IKY_DB)


class User(Document):
    name = StringField(max_length=50, required=True)
    email = EmailField(required=True, unique=True)


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
    user = ReferenceField(User, required=True, reverse_delete_rule=CASCADE)


if __name__ == '__main__':
    newUser = User(name='user')
    newUser.email = 'user@domain'
    newUser.save()

    newStory = Story()
    newStory.storyName = 'test'
    newStory.labels = ['']
    newStory.actionName = 'Test Ok'
    newStory.actionType = '1'
    newStory.user = newUser
    newStory.save()

    newLabeledSentence = LabeledSentences()
    newLabeledSentence.data = [['Test', 'VB', 'O']]
    newStory.labeledSentences.append(newLabeledSentence)
    newStory.save()
