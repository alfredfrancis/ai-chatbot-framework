import os
from flask import Flask,send_from_directory
from flask_cors import CORS
from flask_mongoengine import MongoEngine
from config import config
from app.dialogue_manager.dialogue_manager import DialogueManager

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

    from app.bots.controllers import bots
    from app.nlu.controllers import nlu
    from app.intents.controllers import intents
    from app.train.controllers import train
    from app.chat.controllers import chat
    from app.entities.controllers import entities_blueprint

    app.register_blueprint(nlu)
    app.register_blueprint(intents)
    app.register_blueprint(train)
    app.register_blueprint(chat)
    app.register_blueprint(bots)
    app.register_blueprint(entities_blueprint)

    @app.route('/ready')
    def ready():
        return "ok",200

    @app.route('/<path:path>', methods=['GET'])
    def static_proxy(path):
        return send_from_directory(admin_panel_dist, path)

    @app.route('/')
    def root():
        return send_from_directory(admin_panel_dist, 'index.html')

    @app.errorhandler(404)
    def not_found(error):
        return "Not found", 404

    return app





