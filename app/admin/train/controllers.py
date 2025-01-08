from bson.objectid import ObjectId
from app.repository.intents import Intent
from flask import Blueprint,request, current_app as app, jsonify
from app.bot.nlu.training import train_pipeline


train = Blueprint('train_blueprint', __name__,
                  url_prefix='/train')


@train.route('/<story_id>/data', methods=['POST'])
def save_training_data(story_id):
    """
    Save training data for given story
    :param story_id:
    :return:
    """
    story = Intent.objects.get(id=ObjectId(story_id))
    story.trainingData = request.json
    story.save()
    return jsonify({"result": True})


@train.route('/<story_id>/data', methods=['GET'])
def get_training_data(story_id):
    """
    retrieve training data for a given story
    :param story_id:
    :return:
    """
    story = Intent.objects.get(id=ObjectId(story_id))
    return jsonify(story.trainingData)


@train.route('/build_models', methods=['POST'])
def build_models():
    """
    Build Intent classification and NER Models
    :return:
    """
    train_pipeline(app)
    return jsonify({"result": True})
