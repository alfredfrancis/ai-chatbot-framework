from flask import Blueprint, current_app as app,jsonify

from app.nlu.training import train_pipeline

nlu = Blueprint('nlu_blueprint', __name__, url_prefix='/nlu')


@nlu.route('/build_models', methods=['POST'])
def build_models():
    """
    Build Intent classification and NER Models
    :return:
    """
    train_pipeline(app.config["MODELS_DIR"])
    return jsonify({"result": True})
