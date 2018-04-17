from bson.objectid import ObjectId
from mongoengine.fields import ListField,\
    EmbeddedDocumentListField, EmbeddedDocumentField, EmbeddedDocument,\
    ObjectIdField, StringField,\
    BooleanField, Document





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
