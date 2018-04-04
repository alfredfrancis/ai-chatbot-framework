from bson.objectid import ObjectId
import ast
from flask import Blueprint, request, render_template
import app.commons.buildResponse as buildResponse
from app.stories.models import Story, LabeledSentences

train = Blueprint('train_blueprint', __name__,
                  url_prefix='/train'
                  )



@train.route('/insertLabeledSentence', methods=['POST'])
def insertLabeledSentence():
    story = Story.objects.get(id=ObjectId(request.form['storyId']))
    labeledSentence = LabeledSentences()
    print(ast.literal_eval(request.form['labeledSentence']))
    labeledSentence.data = ast.literal_eval(request.form['labeledSentence'])
    story.labeledSentences.append(labeledSentence)
    try:
        story.save()
    except Exception as e:
        return {"error": e}
    return buildResponse.sentOk()


@train.route('/deleteLabeledSentences', methods=['POST'])
def deleteLabeledSentences():
    story = Story.objects.get(id=ObjectId(request.form['storyId']))
    story.labeledSentences.filter(id=ObjectId(
        request.form['sentenceId'])).delete()
    story.save()
    return buildResponse.sentOk()

@train.route('/<storyId>/data', methods=['POST'])
def save_training_data(storyId):
    """
    Save training data for given story
    :param storyId:
    :return:
    """
    story = Story.objects.get(id=ObjectId(storyId))
    story.trainingData = request.json
    story.save()
    return buildResponse.sentOk()

@train.route('/<storyId>/data', methods=['GET'])
def get_training_data(storyId):
    """
    retrive training data for a given story
    :param storyId:
    :return:
    """
    story = Story.objects.get(id=ObjectId(storyId))
    return buildResponse.buildJson(story.trainingData)
