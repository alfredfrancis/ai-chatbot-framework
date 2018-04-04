from flask import Blueprint
from app.commons import build_response

core = Blueprint('core_blueprint', __name__, url_prefix='/core')


from app.core.tasks import train_models


@core.route('/build_models', methods=['POST'])
def build_models():
    """
    Build Intent classification and NER Models
    :return:
    """
    train_models()
    return build_response.sent_ok()
