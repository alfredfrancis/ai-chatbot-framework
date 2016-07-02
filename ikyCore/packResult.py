from ikyCore.models import Story
from bson.objectid import ObjectId
from ikyCore.functions import dateFromString


def packResult(storyId, extractedEntities):

    story = Story.objects.get(id=ObjectId(storyId))
    story = story.to_mongo().to_dict()

    labelsOriginal = set(story['labels'])
    print (labelsOriginal)

    result = dict()
    result["actionName"] = story['actionName']
    result["actionType"] = story['actionType']

    if len(labelsOriginal) != 0:
        result["entities"] = extractedEntities
        if "date" in result["entities"]:
            result["entities"]["date"] = dateFromString(result["entities"]["date"])
    return result
