from bson.objectid import ObjectId

import interface
from app.commons import errorCodes
from app.core import Story


def packResult(storyId, extractedEntities):
    story = Story.objects.get(id=ObjectId(storyId))
    story = story.to_mongo().to_dict()

    labelsOriginal = set(story['labels'])
    if len(story['labels'][0]) != 0:
        for label in labelsOriginal:
            if label not in extractedEntities:
                return errorCodes.UnableToextractentities

    result = dict()
    result["actionType"] = story['actionType']
    if(story['actionType']=="4"):
        result["ikySays"]= interface.messageTemplate(story['actionName'], extractedEntities)
    else:
        result["actionName"] = story['actionName']



    if len(story['labels'][0]) != 0:
        result["entities"] = extractedEntities
        # if "date" in result["entities"]:
        #     result["entities"]["date"] = dateFromString(result["entities"]["date"])
    else:
        result["entities"] = {}
    return result
