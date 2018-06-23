from mongoengine.fields import Document
from mongoengine.fields import EmbeddedDocument
from mongoengine.fields import EmbeddedDocumentListField
from mongoengine.fields import ListField
from mongoengine.fields import StringField


class EntityValue(EmbeddedDocument):
    value = StringField(required=True)
    synonyms = ListField(required=True, default=[])


class Entity(Document):
    name = StringField(max_length=100, required=True, unique=True)
    entity_values = EmbeddedDocumentListField(EntityValue)
    meta = {
        'indexes': [
            {
                'fields': ['$name'],
                'default_language': 'english'
            }
        ]}
