from flask import Blueprint, request, jsonify, Response, abort
from bson.json_util import dumps, loads
from app.repository.bot import Bot
from app.repository.intents import Intent
from app.repository.entities import Entity
from app.repository.utils import update_document

bots = Blueprint('bots_blueprint', __name__,
                 url_prefix='/bots/<bot_name>')


@bots.route('/config', methods=['PUT'])
def set_config(bot_name):
    """
    Read bot config
    :param bot_name:
    :return:
    """

    content = request.get_json(silent=True)
    bot = Bot.objects.get(name=bot_name)
    bot.config = content
    bot.save()
    return jsonify({"result": True})


@bots.route('/config', methods=['GET'])
def get_config(bot_name):
    """
    Update bot config
    :return:
    """
    bot = Bot.objects.get(name=bot_name)

    return jsonify(bot.config)


@bots.route('/export', methods=['GET'])
def export_agent(bot_name):
    """
    Export all intents and entities for the bot as a JSON file
    :param bot_name: Name of the bot
    :return: JSON file containing all intents and entities
    """
    # Get all intents and entities
    intents_json = loads(Intent.objects.to_json())
    entities_json = loads(Entity.objects.to_json())
    
    # Combine into a single JSON object
    export_data = {
        "intents": intents_json,
        "entities": entities_json
    }
    
    return Response(dumps(export_data),
                   mimetype='application/json',
                   headers={'Content-Disposition': 'attachment;filename=chatbot_data.json'})


@bots.route('/import', methods=['POST'])
def import_agent(bot_name):
    """
    Import intents and entities from a JSON file for the bot
    :param bot_name: Name of the bot
    :return: Number of intents and entities created
    """
    if 'file' not in request.files:
        abort(400, 'No file part')
    json_file = request.files['file']
    created_intents, created_entities = import_json(json_file)
    return jsonify({
        "num_intents_created": len(created_intents),
        "num_entities_created": len(created_entities)
    })


def import_json(json_file):
    """
    Helper function to import intents and entities from JSON
    :param json_file: The uploaded JSON file
    :return: Tuple of (created_intents, created_entities)
    """
    json_data = loads(json_file.read())
    
    # Import intents
    created_intents = []
    if "intents" in json_data:
        for intent in json_data["intents"]:
            new_intent = Intent()
            new_intent = update_document(new_intent, intent)
            new_intent.save()
            created_intents.append(new_intent)
    
    # Import entities
    created_entities = []
    if "entities" in json_data:
        for entity in json_data["entities"]:
            new_entity = Entity()
            new_entity = update_document(new_entity, entity)
            new_entity.save()
            created_entities.append(new_entity)
    
    return created_intents, created_entities
