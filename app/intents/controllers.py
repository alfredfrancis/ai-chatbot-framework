import os
from bson.json_util import dumps
from bson.objectid import ObjectId
from flask import Blueprint, request, Response
from flask import current_app as app
from app.commons import build_response
from app.intents.models import Intent, Parameter, ApiDetails
from app.commons.utils import update_document


intents = Blueprint('intents_blueprint', __name__,
                    url_prefix='/intents')


@intents.route('/', methods=['POST'])
def create_intent():
    """
    Create a story from the provided json
    :param json:
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
    intents = Intent.objects
    return build_response.sent_json(intents.to_json())


@intents.route('/<id>')
def read_intent(id):
    """
    Find details for the given intent id
    :param id:
    :return:
    """
    return Response(response=dumps(
        Intent.objects.get(
            id=ObjectId(
                id)).to_mongo().to_dict()),
        status=200,
        mimetype="application/json")


@intents.route('/<id>', methods=['PUT'])
def update_intent(id):
    """
    Update a story from the provided json
    :param intent_id:
    :param json:
    :return:
    """
    json_data = loads(request.get_data())
    intent = Intent.objects.get(id=ObjectId(id))
    intent = update_document(intent, json_data)
    intent.save()
    return 'success', 200


from app.nlu.tasks import train_models


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

    # remove NER model for the deleted stoy
    try:
        os.remove("{}/{}.model".format(app.config["MODELS_DIR"], id))
    except OSError:
        pass
    return build_response.sent_ok()


from flask import send_file
import StringIO


@intents.route('/export', methods=['GET'])
def export_intents():
    """
    Deserialize and export Mongoengines as jsonfile
    :return:
    """
    strIO = StringIO.StringIO()
    strIO.write(Intent.objects.to_json())
    strIO.seek(0)
    return send_file(strIO,
                     attachment_filename="iky_intents.json",
                     as_attachment=True)


from flask import abort
from bson.json_util import loads


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
    intents = import_json(json_file)

    return build_response.build_json({"num_intents_created": len(intents)})


def import_json(json_file):
    json_data = json_file.read()
    # intents = Intent.objects.from_json(json_data)
    intents = loads(json_data)

    creates_intents = []
    for intent in intents:
        new_intent = Intent()
        new_intent = update_document(new_intent, intent)
        new_intent.save()
        creates_intents.append(new_intent)
    return creates_intents