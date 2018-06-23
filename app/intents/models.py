from bson.objectid import ObjectId
from mongoengine.fields import BooleanField
from mongoengine.fields import Document
from mongoengine.fields import EmbeddedDocument
from mongoengine.fields import EmbeddedDocumentField
from mongoengine.fields import EmbeddedDocumentListField
from mongoengine.fields import ListField
from mongoengine.fields import ObjectIdField
from mongoengine.fields import StringField


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
    headers = ListField(default=[])
    isJson = BooleanField(default=False)
    jsonData = StringField(default="{}")

    def get_headers(self):
        headers = {}
        for header in self.headers:
            headers[header["headerKey"]] = header["headerValue"]
        return headers


class Intent(Document):
    name = StringField(max_length=100, required=True, unique=True)
    userDefined = BooleanField(default=True)
    intentId = StringField(required=True, unique=True)
    apiTrigger = BooleanField(required=True)
    apiDetails = EmbeddedDocumentField(ApiDetails)
    speechResponse = StringField(required=True)
    parameters = ListField(EmbeddedDocumentField(Parameter))
    labeledSentences = EmbeddedDocumentListField(LabeledSentences)
    trainingData = ListField(required=False)
