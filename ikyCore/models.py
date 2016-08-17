from mongoengine import *
from config import *
from bson.objectid import ObjectId

connect(
    IKY_DB,
    host='mongodb://172.30.10.141:27017/iky2',
    port=27017
)


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
    actionName = StringField(max_length=50, required=True)
    labeledSentences = EmbeddedDocumentListField(LabeledSentences)
    user = ReferenceField(User, required=True, reverse_delete_rule=CASCADE)


class Logs(Document):
    user = ReferenceField(User, required=True)
    time = DateTimeField(required=True)
    activity = DictField(required=True)


if __name__ == '__main__':
    newUser = User(name='Iky')
    newUser.email = 'iky@pealdatadirect.com'
    newUser.save()

    newStory = Story()
    newStory.storyName = 'Hello world'
    newStory.labels = ['firstName', 'lastName']
    newStory.actionName = 'sayHello'
    newStory.actionType = '1'
    newStory.user = newUser
    newStory.save()

    newLabeledSentence = LabeledSentences()
    newLabeledSentence.data = [['hello', 'VB', 'O'], ['haai', 'VB', 'O']]
    newStory.labeledSentences.append(newLabeledSentence)
    newStory.save()
