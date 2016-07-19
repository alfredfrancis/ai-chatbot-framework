from bson.objectid import ObjectId

from ikyCore.models import Story
from ikyCore.functions import dateFromString

from ikyCommons import errorCodes


def packResult(storyId, extractedEntities):
    story = Story.objects.get(id=ObjectId(storyId))
    story = story.to_mongo().to_dict()

    labelsOriginal = set(story['labels'])
    if len(story['labels'][0]) != 0:
        for label in labelsOriginal:
            if label not in extractedEntities:
                return errorCodes.UnableToextractentities

    result = dict()
    result["actionName"] = story['actionName']
    result["actionType"] = story['actionType']

    if len(story['labels'][0]) != 0:
        result["entities"] = extractedEntities
        if "date" in result["entities"]:
            result["entities"]["date"] = dateFromString(result["entities"]["date"])
    else:
        result["entities"] = {}
    return result
