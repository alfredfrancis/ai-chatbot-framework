from mongoengine import *
from config import *
from bson.objectid import ObjectId
from mongoengine import fields

def update_document(document, data_dict):

    def field_value(field, value):

        if field.__class__ in (fields.ListField, fields.SortedListField):
            return [
                field_value(field.field, item)
                for item in value
            ]
        if field.__class__ in (
            fields.EmbeddedDocumentField,
            fields.GenericEmbeddedDocumentField,
            fields.ReferenceField,
            fields.GenericReferenceField
        ):
            return field.document_type(**value)
        else:
            return value

    [setattr(
        document, key,
        field_value(document._fields[key], value)
    ) for key, value in data_dict.items()]

    return document

connect(IKY_DB,host=IKY_DB_HOST)


class LabeledSentences(EmbeddedDocument):
    id = ObjectIdField(required=True, default=lambda: ObjectId())
    data = ListField(required=True)

class Parameter(EmbeddedDocument):
    id = ObjectIdField(default=lambda: ObjectId())
    name = StringField(required=True)
    required = BooleanField(default=False)
    prompt = StringField()

class Story(Document):
    storyName = StringField(max_length=100, required=True, unique=True)
    intentName = StringField(required=True)
    speechResponse = StringField(required=True)
    parameters = EmbeddedDocumentListField(Parameter)
    labeledSentences = EmbeddedDocumentListField(LabeledSentences)


if __name__ == '__main__':

    newStory = Story()
    newStory.storyName = 'Default Fallback intent'
    newStory.intentName = 'fallback'
    newStory.speechResponse = 'Sorry i dont understand'
    newLabeledSentence = LabeledSentences()
    newLabeledSentence.data = [[' ', 'VB', 'O'],['    ', 'VB', 'O']]
    newStory.labeledSentences.append(newLabeledSentence)
    newStory.save()

    newStory = Story()
    newStory.storyName = 'cancel'
    newStory.intentName = 'cancel'
    newStory.speechResponse = "Ok. Canceled."
    newLabeledSentence = LabeledSentences()
    newLabeledSentence.data = [['cancel', 'VB', 'O'],['close', 'VB', 'O']]
    newStory.labeledSentences.append(newLabeledSentence)
    newStory.save()
