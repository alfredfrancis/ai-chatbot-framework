from bson.json_util import dumps, loads
from bson.objectid import ObjectId
from flask import Blueprint, request, Response, jsonify
from app.commons.utils import update_document
from app.entities.models import Entity

entities_blueprint = Blueprint('entities_blueprint', __name__,
                               url_prefix='/entities')


@entities_blueprint.route('/', methods=['POST'])
def create_entity():
    """
    Create a story from the provided json
    :return:
    """
    content = request.get_json(silent=True)

    entity = Entity()
    entity.name = content.get("name")
    entity.entity_values = []

    try:
        entity_id = entity.save()
    except Exception as e:
        return jsonify({"error": str(e)})

    return jsonify({
        "_id": str(entity_id.id)
    })


@entities_blueprint.route('/')
def read_entities():
    """
    find list of entities
    :return:
    """
    intents = Entity.objects.only('name', 'id')
    return  Response(response=intents.to_json(),
                     status=200,
                     mimetype="application/json")


@entities_blueprint.route('/<id>')
def read_entity(id):
    """
    Find details for the given entity name
    :param id:
    :return:
    """
    return Response(
        response=dumps(Entity.objects.get(
            id=ObjectId(id)).to_mongo().to_dict()),
        status=200, mimetype="application/json")


@entities_blueprint.route('/<id>', methods=['PUT'])
def update_entity(id):
    """
    Update a story from the provided json
    :param id:
    :return:
    """
    json_data = loads(request.get_data())
    entity = Entity.objects.get(id=ObjectId(id))
    entity = update_document(entity, json_data)
    entity.save()
    return jsonify({"result": True})


@entities_blueprint.route('/<id>', methods=['DELETE'])
def delete_entity(id):
    """
    Delete a intent
    :param id:
    :return:
    """
    Entity.objects.get(id=ObjectId(id)).delete()

    return jsonify({"result": True})
