from bson.objectid import ObjectId
from mongoengine import *
from mongoengine import fields


connect(DB_NAME, host=DB_HOST)


def update_document(document, data_dict):

    def field_value(field, value):

        if field.__class__ in (fields.ListField, fields.SortedListField,fields.EmbeddedDocumentListField):
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
        document, key.replace("_id","id"),
        field_value(document._fields[key.replace("_id","id")], value)
    ) for key, value in data_dict.items()]

    return document


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
    parameters = ListField(EmbeddedDocumentField(Parameter))
    labeledSentences = EmbeddedDocumentListField(LabeledSentences)
