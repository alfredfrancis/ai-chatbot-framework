from datetime import datetime

import parsedatetime as pdt
from mongoengine.fields import EmbeddedDocumentField
from mongoengine.fields import EmbeddedDocumentListField
from mongoengine.fields import GenericEmbeddedDocumentField
from mongoengine.fields import GenericReferenceField
from mongoengine.fields import ListField
from mongoengine.fields import ReferenceField
from mongoengine.fields import SortedListField


def date_from_string(timeString):
    cal = pdt.Calendar()
    now = datetime.now()
    result = str(cal.parseDT(timeString.strip(), now)[0])
    return result


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


def is_list_empty(inList):
    if isinstance(inList, list):  # Is a list
        return all(map(is_list_empty, inList))
    return False  # Not a list
