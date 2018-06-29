import os
from StringIO import StringIO

from bson.json_util import dumps
from bson.json_util import loads
from bson.objectid import ObjectId
from flask import Blueprint, request, Response
from flask import abort
from flask import current_app as app
from flask import send_file

from app.commons import build_response
from app.commons.utils import update_document
from app.intents.models import ApiDetails
from app.intents.models import Intent
from app.intents.models import Parameter
from app.nlu.tasks import train_models

intents = Blueprint('intents_blueprint', __name__,
                    url_prefix='/intents')


@intents.route('/', methods=['POST'])
def create_intent():
    """
    Create a story from the provided json
    :return:
    """
    content = request.get_json(silent=True)

    intent = Intent()
    intent.name = content.get("name")
    intent.intentId = content.get("intentId")
    intent.speechResponse = content.get("speechResponse")
    intent.trainingData = []

    if content.get("apiTrigger") is True:
        intent.apiTrigger = True
        api_details = ApiDetails()
        isJson = content.get("apiDetails").get("isJson")
        api_details.isJson = isJson
        if isJson:
            api_details.jsonData = content.get("apiDetails").get("jsonData")

        api_details.url = content.get("apiDetails").get("url")
        api_details.headers = content.get("apiDetails").get("headers")
        api_details.requestType = content.get("apiDetails").get("requestType")
        intent.apiDetails = api_details
    else:
        intent.apiTrigger = False

    if content.get("parameters"):
        for param in content.get("parameters"):
            parameter = Parameter()
            update_document(parameter, param)
            intent.parameters.append(parameter)
    try:
        story_id = intent.save()
    except Exception as e:
        return build_response.build_json({"error": str(e)})

    return build_response.build_json({
        "_id": str(story_id.id)
    })


@intents.route('/')
def read_intents():
    """
    find list of intents for the agent
    :return:
    """
    all_intents = Intent.objects
    return build_response.sent_json(all_intents.to_json())


@intents.route('/<id>')
def read_intent(id):
    """
    Find details for the given intent id
    :param id:
    :return:
    """
    return Response(response=dumps(
        Intent.objects.get(
            id=ObjectId(id)).to_mongo().to_dict()),
        status=200,
        mimetype="application/json")


@intents.route('/<id>', methods=['PUT'])
def update_intent(id):
    """
    Update a story from the provided json
    :return:
    """
    json_data = loads(request.get_data())
    intent = Intent.objects.get(id=ObjectId(id))
    intent = update_document(intent, json_data)
    intent.save()
    return 'success', 200


@intents.route('/<id>', methods=['DELETE'])
def delete_intent(id):
    """
    Delete a intent
    :param id:
    :return:
    """
    Intent.objects.get(id=ObjectId(id)).delete()

    try:
        train_models()
    except BaseException:
        pass

    # remove NER model for the deleted story
    try:
        os.remove("{}/{}.model".format(app.config["MODELS_DIR"], id))
    except OSError:
        pass
    return build_response.sent_ok()


@intents.route('/export', methods=['GET'])
def export_intents():
    """
    Deserialize and export Mongoengines as jsonfile
    :return:
    """
    try:
        strIO = StringIO.StringIO()
    except AttributeError:
        strIO = StringIO()

    strIO.write(Intent.objects.to_json())
    strIO.seek(0)
    return send_file(strIO,
                     attachment_filename="iky_intents.json",
                     as_attachment=True)


@intents.route('/import', methods=['POST'])
def import_intents():
    """
    Convert json files to Intents objects and insert to MongoDB
    :return:
    """
    # check if the post request has the file part
    if 'file' not in request.files:
        abort(400, 'No file part')
    json_file = request.files['file']
    all_intents = import_json(json_file)

    return build_response.build_json({"num_intents_created": len(all_intents)})


def import_json(json_file):
    json_data = json_file.read()
    # intents = Intent.objects.from_json(json_data)
    all_intents = loads(json_data)

    creates_intents = []
    for intent in all_intents:
        new_intent = Intent()
        new_intent = update_document(new_intent, intent)
        new_intent.save()
        creates_intents.append(new_intent)
    return creates_intents
