from flask import Blueprint
from app.commons import buildResponse

core = Blueprint('core_blueprint', __name__, url_prefix='/core')


from app.core.tasks import train_models

@core.route('/buildModels', methods=['POST'])
def buildModels():
    """
    Build Intent classification and NER Models
    :return:
    """
    train_models()
    return buildResponse.sentOk()