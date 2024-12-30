from flask import Blueprint

from app.commons import build_response
from app.nlu.tasks import train_models
from flask import Blueprint, current_app as app

nlu = Blueprint('nlu_blueprint', __name__, url_prefix='/nlu')


@nlu.route('/build_models', methods=['POST'])
def build_models():
    """
    Build Intent classification and NER Models
    :return:
    """
    train_models(app)
    return build_response.sent_ok()
