from mongoengine.fields import ListField,\
    EmbeddedDocumentListField, EmbeddedDocument,\
    ObjectIdField, StringField,Document


class EntityValue(EmbeddedDocument):
    value = StringField(required=True)
    synonyms = ListField(required=True,default=[])

class Entity(Document):
    name = StringField(max_length=100, required=True, unique=True)
    entity_values = EmbeddedDocumentListField(EntityValue)
    meta = {
        'indexes': [
        {'fields': ['$name'],
         'default_language': 'english'
        }
    ]}
