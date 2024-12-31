from flask import Blueprint, request, jsonify

from app.agents.models import Bot

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
    return jsonify({"result": True})


@bots.route('/config', methods=['GET'])
def get_config(bot_name):
    """
    Update bot config
    :return:
    """
    bot = Bot.objects.get(name=bot_name)

    return jsonify(bot.config)
