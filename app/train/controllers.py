from bson.objectid import ObjectId
import ast

from flask import Blueprint, request, render_template

import app.commons.buildResponse as buildResponse
from app.stories.models import Story,LabeledSentences

from app.core.intentClassifier import IntentClassifier

train = Blueprint('train', __name__, url_prefix='/train')

@train.route('/train', methods=['GET'])
def train():
    _id = request.args.get("storyId")
    story = Story.objects.get(id=ObjectId(_id))
    labeledSentences = story.labeledSentences
    return render_template('train/train.html',
                           storyId=_id,
                           labeledSentences=labeledSentences,
                           story=story.to_mongo().to_dict(),
                           parameters=[parameter.name for parameter in story.parameters]
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
    story.labeledSentences.filter(id=ObjectId(request.form['sentenceId'])).delete()
    story.save()
    return buildResponse.sentOk()