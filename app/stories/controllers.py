import os
from bson.json_util import dumps
from bson.objectid import ObjectId
from flask import Blueprint, request, Response
from flask import current_app as app
import app.commons.buildResponse as buildResponse
from app.stories.models import Story, Parameter, ApiDetails, update_document



stories = Blueprint('stories_blueprint', __name__,
                    url_prefix='/stories')

@stories.route('/', methods=['POST'])
def createStory():
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
        apiDetails = ApiDetails()
        isJson = content.get("apiDetails").get("isJson")
        apiDetails.isJson = isJson
        if isJson:
            apiDetails.jsonData = content.get("apiDetails").get("jsonData")

        apiDetails.url = content.get("apiDetails").get("url")
        apiDetails.requestType = content.get("apiDetails").get("requestType")
        story.apiDetails = apiDetails
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
        return buildResponse.buildJson({"error": str(e)})

    return buildResponse.buildJson({
        "_id":str(story_id.id)
    })


@stories.route('/')
def readStories():
    """
    find list of stories for the agent
    :return:
    """
    stories = Story.objects
    return buildResponse.sentJson(stories.to_json())


@stories.route('/<storyId>')
def readStory(storyId):
    """
    Find details for the given storyId
    :param storyId:
    :return:
    """
    return Response(response=dumps(
        Story.objects.get(
            id=ObjectId(
                storyId)).to_mongo().to_dict()),
        status=200,
        mimetype="application/json")


@stories.route('/<storyId>', methods=['PUT'])
def updateStory(storyId):
    """
    Update a story from the provided json
    :param storyId:
    :param json:
    :return:
    """
    jsondata = loads(request.get_data())
    story = Story.objects.get(id=ObjectId(storyId))
    story = update_document(story, jsondata)
    story.save()
    return 'success', 200

from app.core.tasks import train_models

@stories.route('/<storyId>', methods=['DELETE'])
def deleteStory(storyId):
    """
    Delete a story
    :param storyId:
    :return:
    """
    Story.objects.get(id=ObjectId(storyId)).delete()

    try:
        train_models()
    except BaseException:
        pass

    # remove NER model for the deleted stoy
    try:
        os.remove("{}/{}.model".format(app.config["MODELS_DIR"], storyId))
    except OSError:
        pass
    return buildResponse.sentOk()

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
        abort(400,'No file part')
    file = request.files['file']

    json_data = file.read()
    # stories = Story.objects.from_json(json_data)
    stories = loads(json_data)
    for story in stories:
        new_story = Story()
        new_story = update_document(new_story,story)
        new_story.save()
    return buildResponse.buildJson({"no_stories_created":len(stories)})