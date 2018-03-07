from bson.objectid import ObjectId
import ast
from flask import Blueprint, request, render_template, g
import app.commons.buildResponse as buildResponse
from app.stories.models import Story, LabeledSentences
from app.core.controllers import requires_auth

train = Blueprint('train_blueprint', __name__,
                  url_prefix='/train',
                  template_folder='templates',
                  static_folder='static'
                  )


@train.route('/<storyId>', methods=['GET'])
@requires_auth
def home(storyId):
    story = Story.objects.filter(id=ObjectId(storyId))
    if g.botId:
        story=story.filter(bot=g.botId)
    story = story.get()
    labeledSentences = story.labeledSentences
    return render_template(
        'train.html',
        storyId=storyId,
        labeledSentences=labeledSentences,
        story=story.to_mongo().to_dict(),
        parameters=[
            parameter.name for parameter in story.parameters])


@train.route('/insertLabeledSentence', methods=['POST'])
@requires_auth
def insertLabeledSentence():
    story = Story.objects.get(id=ObjectId(request.form['storyId']), bot=g.botId)
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
@requires_auth
def deleteLabeledSentences():
    story = Story.objects.get(id=ObjectId(request.form['storyId']), bot=g.botId)
    story.labeledSentences.filter(id=ObjectId(
        request.form['sentenceId'])).delete()
    story.save()
    return buildResponse.sentOk()
