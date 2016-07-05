from bson.objectid import ObjectId

from ikyCore.models import Story
from ikyCore.functions import dateFromString

from ikyCommons import errorCodes


def packResult(storyId, extractedEntities):
    story = Story.objects.get(id=ObjectId(storyId))
    story = story.to_mongo().to_dict()

    labelsOriginal = set(story['labels'])

    for label in labelsOriginal:
        if label not in extractedEntities:
            return errorCodes.UnableToextractentities

    result = dict()
    result["actionName"] = story['actionName']
    result["actionType"] = story['actionType']

    if len(labelsOriginal) != 0:
        result["entities"] = extractedEntities
        if "date" in result["entities"]:
            result["entities"]["date"] = dateFromString(result["entities"]["date"])
    return result
