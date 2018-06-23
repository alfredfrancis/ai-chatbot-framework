from mongoengine.fields import DictField
from mongoengine.fields import Document
from mongoengine.fields import StringField


class Bot(Document):
    name = StringField(max_length=100, required=True, unique=True)
    config = DictField(required=True, default={
        "confidence_threshold": .70
    })
