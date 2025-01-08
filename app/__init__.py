import os
from flask import Flask, send_from_directory, Blueprint
from flask_cors import CORS
from flask_mongoengine import MongoEngine
from config import config
from app.bot.dialogue_manager.dialogue_manager import DialogueManager

admin_panel_dist = 'static/'

db = MongoEngine()

def create_app(env="Development"):
    app = Flask(__name__)

    # Configurations
    try:
        env = os.environ['APPLICATION_ENV']
    except KeyError as e:
        app.logger.info('Unknown environment key, defaulting to Development')

    app.config.from_object(config[env])
    app.config.from_prefixed_env(prefix='APP')

    CORS(app)
    db.init_app(app)

    # initialize dialogue_manager
    dialogue_manager = DialogueManager.from_config(app)
    dialogue_manager.update_model(app.config["MODELS_DIR"])
    app.dialogue_manager : DialogueManager = dialogue_manager

    from app.admin.bots.controllers import bots
    from app.admin.intents.controllers import intents
    from app.admin.train.controllers import train
    from app.bot.chat.controllers import chat
    from app.admin.entities.controllers import entities_blueprint

    # bot endpoints
    # TODO: move to a isolated web server
    app.register_blueprint(chat)

    # admin endpoints
    admin_routes = Blueprint('admin', __name__, url_prefix='/admin/')
    admin_routes.register_blueprint(intents)
    admin_routes.register_blueprint(train)
    admin_routes.register_blueprint(bots)
    admin_routes.register_blueprint(entities_blueprint)
    app.register_blueprint(admin_routes)


    @app.route('/ready')
    def ready():
        return "ok",200

    @app.route('/<path:path>', methods=['GET'])
    def static_proxy(path):
        return send_from_directory(admin_panel_dist, path)

    @app.errorhandler(404)
    def not_found(error):
        return "Not found", 404

    return app





