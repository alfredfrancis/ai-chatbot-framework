import os
from bson.json_util import dumps
from bson.objectid import ObjectId
from flask import Blueprint, request, Response
from flask import current_app as app
from app.commons import build_response
from app.stories.models import Story, Parameter, ApiDetails, update_document


stories = Blueprint('stories_blueprint', __name__,
                    url_prefix='/stories')


@stories.route('/', methods=['POST'])
def create_story():
    """
    Create a story from the provided json
    :param json:
    :return:
    """
    content = request.get_json(silent=True)

    story = Story()
    story.storyName = content.get("storyName")
    story.intentName = content.get("intentName")
    story.speechResponse = content.get("speechResponse")
    story.trainingData = []

    if content.get("apiTrigger") is True:
        story.apiTrigger = True
        api_details = ApiDetails()
        isJson = content.get("apiDetails").get("isJson")
        api_details.isJson = isJson
        if isJson:
            api_details.jsonData = content.get("apiDetails").get("jsonData")

        api_details.url = content.get("apiDetails").get("url")
        api_details.requestType = content.get("apiDetails").get("requestType")
        story.apiDetails = api_details
    else:
        story.apiTrigger = False

    if content.get("parameters"):
        for param in content.get("parameters"):
            parameter = Parameter()
            update_document(parameter, param)
            story.parameters.append(parameter)
    try:
        story_id = story.save()
    except Exception as e:
        return build_response.build_json({"error": str(e)})

    return build_response.build_json({
        "_id": str(story_id.id)
    })


@stories.route('/')
def read_stories():
    """
    find list of stories for the agent
    :return:
    """
    stories = Story.objects
    return build_response.sent_json(stories.to_json())


@stories.route('/<story_id>')
def read_story(story_id):
    """
    Find details for the given storyId
    :param story_id:
    :return:
    """
    return Response(response=dumps(
        Story.objects.get(
            id=ObjectId(
                story_id)).to_mongo().to_dict()),
        status=200,
        mimetype="application/json")


@stories.route('/<story_id>', methods=['PUT'])
def update_story(story_id):
    """
    Update a story from the provided json
    :param story_id:
    :param json:
    :return:
    """
    json_data = loads(request.get_data())
    story = Story.objects.get(id=ObjectId(story_id))
    story = update_document(story, json_data)
    story.save()
    return 'success', 200


from app.nlu.tasks import train_models


@stories.route('/<story_id>', methods=['DELETE'])
def delete_story(story_id):
    """
    Delete a story
    :param story_id:
    :return:
    """
    Story.objects.get(id=ObjectId(story_id)).delete()

    try:
        train_models()
    except BaseException:
        pass

    # remove NER model for the deleted stoy
    try:
        os.remove("{}/{}.model".format(app.config["MODELS_DIR"], story_id))
    except OSError:
        pass
    return build_response.sent_ok()


from flask import send_file
import StringIO


@stories.route('/export', methods=['GET'])
def export_stories():
    """
    Deserialize and export Mongoengines as jsonfile
    :return:
    """
    strIO = StringIO.StringIO()
    strIO.write(Story.objects.to_json())
    strIO.seek(0)
    return send_file(strIO,
                     attachment_filename="iky_stories.json",
                     as_attachment=True)


from flask import abort
from bson.json_util import loads


@stories.route('/import', methods=['POST'])
def import_stories():
    """
    Convert json files to Stories objects and insert to MongoDB
    :return:
    """
    # check if the post request has the file part
    if 'file' not in request.files:
        abort(400, 'No file part')
    json_file = request.files['file']
    stories = import_json(json_file)

    return build_response.build_json({"no_stories_created": len(stories)})


def import_json(json_file):
    json_data = json_file.read()
    # stories = Story.objects.from_json(json_data)
    stories = loads(json_data)

    creates_stories = []
    for story in stories:
        new_story = Story()
        new_story = update_document(new_story, story)
        new_story.save()
        creates_stories.append(new_story)
    return creates_stories