from flask import Blueprint, request

from app.agents.models import Bot
from app.commons import build_response

bots = Blueprint('bots_blueprint', __name__,
                 url_prefix='/agents/<bot_name>')


@bots.route('/config', methods=['PUT'])
def set_config(bot_name):
    """
    Read bot config
    :param bot_name:
    :return:
    """

    content = request.get_json(silent=True)
    bot = Bot.objects.get(name=bot_name)
    bot.config = content
    bot.save()
    return build_response.sent_ok()


@bots.route('/config', methods=['GET'])
def get_config(bot_name):
    """
    Update bot config
    :return:
    """
    bot = Bot.objects.get(name=bot_name)

    return build_response.build_json(bot.config)
