from ikyCore.models import Story
from bson.objectid import ObjectId
from ikyCore.functions import dateFromString


def packResult(storyId, extractedEntities):

    story = Story.objects.get(id=ObjectId(storyId))
    story = story.to_mongo().to_dict()

    labelsOriginal = set(story['labels'])

    result = dict()
    result["actionName"] = story['actionName']
    result["actionType"] = story['actionType']

    if len(labelsOriginal) != 0:
        result["labels"] = extractedEntities
        if "date" in result["labels"]:
            result["labels"]["date"] = dateFromString(result["labels"]["date"])
    return result
