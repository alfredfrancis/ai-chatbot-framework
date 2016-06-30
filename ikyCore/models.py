from mongoengine import *
from config import *

connect(IKY_DB)


class User(Document):
    Name = StringField(max_length=50, required=True)
    email = EmailField(required=True, unique=True)


ACTIONTYPE = (('1', 'Function'),
              ('2', 'SQL query'),
              ('3', 'REST API'),
              ('4', 'Custom Message'))


class LabeledQueries(EmbeddedDocument):
    data = MultiPointField(required=True)


class Story(Document):
    storyName = StringField(max_length=100, required=True, unique=True)
    labels = ListField(StringField())
    actionType = StringField(choices=ACTIONTYPE, required=True)
    actionName = StringField(max_length=50, required=True)
    labeledQueries = ListField(EmbeddedDocumentField(LabeledQueries))
    user = ReferenceField(User, required=True)


newUser = User(Name='Alfred Francis')
newUser.email = 'alfred.francis@pealdatadirect.com'
newUser.save()

newStory = Story()
newStory.storyName = 'Hello world'
newStory.labels = ['firstName', 'lastName']
newStory.actionName = 'sayHello'
newStory.actionType = '1'
newStory.user = newUser
newStory.save()

newLabeledData = LabeledQueries()
newLabeledData.data = [['hello', 'VB', 'O'], ['haai', 'VB', 'O']]
newLabeledData.story = newStory
newLabeledData.save()
