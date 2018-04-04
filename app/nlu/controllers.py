from flask import Blueprint
from app.commons import build_response

nlu = Blueprint('nlu_blueprint', __name__, url_prefix='/nlu')


from app.nlu.tasks import train_models


@nlu.route('/build_models', methods=['POST'])
def build_models():
    """
    Build Intent classification and NER Models
    :return:
    """
    train_models()
    return build_response.sent_ok()
