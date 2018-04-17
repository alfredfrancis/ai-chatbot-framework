from mongoengine.fields import ListField,\
    EmbeddedDocumentListField, EmbeddedDocument,\
    ObjectIdField, StringField,Document


class EntityValue(EmbeddedDocument):
    value = ObjectIdField(required=True)
    synonyms = ListField(required=True)

class Entity(Document):
    name = StringField(max_length=100, required=True, unique=True)
    values = EmbeddedDocumentListField(EntityValue)
