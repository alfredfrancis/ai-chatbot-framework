from bson.objectid import ObjectId
from mongoengine.fields import ListField, SortedListField,\
    EmbeddedDocumentListField, EmbeddedDocumentField,\
    GenericEmbeddedDocumentField, ReferenceField,\
    GenericReferenceField, EmbeddedDocument,\
    ObjectIdField, StringField,\
    BooleanField, Document


def update_document(document, data_dict):
    """
    Recreate Document object from python dictionary
    :param document:
    :param data_dict:
    :return:
    """

    def field_value(field, value):

        if field.__class__ in (
                ListField,
                SortedListField,
                EmbeddedDocumentListField):
            return [
                field_value(field.field, item)
                for item in value
            ]
        if field.__class__ in (
            EmbeddedDocumentField,
            GenericEmbeddedDocumentField,
            ReferenceField,
            GenericReferenceField
        ):
            return field.document_type(**value)
        else:
            return value

    [setattr(
        document, key.replace("_id", "id"),
        field_value(document._fields[key.replace("_id", "id")], value)
    ) for key, value in data_dict.items()]

    return document


class LabeledSentences(EmbeddedDocument):
    id = ObjectIdField(required=True, default=lambda: ObjectId())
    data = ListField(required=True)


class Parameter(EmbeddedDocument):
    id = ObjectIdField(default=lambda: ObjectId())
    name = StringField(required=True)
    required = BooleanField(default=False)
    type = StringField(required=False)
    prompt = StringField()


class ApiDetails(EmbeddedDocument):
    url = StringField(required=True)
    requestType = StringField(
        choices=[
            "POST",
            "GET",
            "DELETE",
            "PUT"],
        required=True)
    isJson = BooleanField(default=False)
    jsonData = StringField(default="{}")


class Intent(Document):
    name = StringField(max_length=100, required=True, unique=True)
    intentId = StringField(required=True)
    apiTrigger = BooleanField(required=True)
    apiDetails = EmbeddedDocumentField(ApiDetails)
    speechResponse = StringField(required=True)
    parameters = ListField(EmbeddedDocumentField(Parameter))
    labeledSentences = EmbeddedDocumentListField(LabeledSentences)
    trainingData = ListField(required=False)
