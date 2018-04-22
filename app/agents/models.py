from mongoengine.fields import StringField , Document,DictField

class Bot(Document):
    name = StringField(max_length=100, required=True, unique=True)
    config = DictField(required=True,default={
        "confidence_threshold": .70
    })