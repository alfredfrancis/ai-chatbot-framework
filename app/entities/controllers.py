import os
from bson.json_util import dumps
from bson.objectid import ObjectId
from flask import Blueprint, request, Response
from flask import current_app as app
from app.commons import build_response
from app.entities.models import Entity

from app.commons.functions import update_document

intents = Blueprint('entities_blueprint', __name__,
                    url_prefix='/entities')


@intents.route('/', methods=['POST'])
def create_entity():
    """
    Create a story from the provided json
    :param json:
    :return:
    """
    content = request.get_json(silent=True)

    entity = Entity()
    entity.name = content.get("name")
    entity.values = []

    try:
        entity_id = entity.save()
    except Exception as e:
        return build_response.build_json({"error": str(e)})

    return build_response.build_json({
        "_id": str(entity_id.id)
    })


@intents.route('/')
def read_entities():
    """
    find list of entities
    :return:
    """
    intents = Entity.objects
    return build_response.sent_json(intents.to_json())


@intents.route('/<name>')
def read_entity(name):
    """
    Find details for the given entity name
    :param id:
    :return:
    """
    return Response(response=dumps(
        Entity.objects.get(
            name=name).to_mongo().to_dict()),
        status=200,
        mimetype="application/json")


@intents.route('/<name>', methods=['PUT'])
def update_entity(name):
    """
    Update a story from the provided json
    :param intent_id:
    :param json:
    :return:
    """
    json_data = loads(request.get_data())
    entity = Entity.objects.get(id=ObjectId(id))
    entity = update_document(entity, json_data)
    entity.save()
    return 'success', 200


@intents.route('/<name>', methods=['DELETE'])
def delete_entity(name):
    """
    Delete a intent
    :param id:
    :return:
    """
    Entity.objects.get(name=name).delete()

    return build_response.sent_ok()