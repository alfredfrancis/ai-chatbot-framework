import os
from flask import Flask,send_from_directory
from flask_cors import CORS
from flask_mongoengine import MongoEngine

APP_ROOT = os.path.dirname(os.path.abspath(__file__ + "../../"))

db = MongoEngine()

spacy_tokenizer = None

def create_app(env = 'Development'):
    app = Flask(__name__)
    CORS(app)
    # Configurations
    try:
        env = os.environ['APPLICATION_ENV']
    except KeyError as e:
        app.logger.info('Unknown environment key, defaulting to Development')
        
    app.config.from_object('config.%s' % env)
    db.init_app(app)

    import spacy
    global spacy_tokenizer
    spacy_tokenizer = spacy.load(app.config["SPACY_LANG_MODEL"])

    from app.agents.controllers import bots
    from app.nlu.controllers import nlu
    from app.intents.controllers import intents
    from app.train.controllers import train
    from app.endpoint.controllers import endpoint
    from app.entities.controllers import entities_blueprint

    app.register_blueprint(nlu)
    app.register_blueprint(intents)
    app.register_blueprint(train)
    app.register_blueprint(endpoint)
    app.register_blueprint(bots)
    app.register_blueprint(entities_blueprint)

    admin_panel_dist = os.path.join(APP_ROOT, 'frontend/dist/')

    @app.route('/ready')
    def ready():
        return "ok",200

    @app.route('/<path:path>', methods=['GET'])
    def static_proxy(path):
        return send_from_directory(admin_panel_dist, path)

    @app.route('/')
    def root():
        print(admin_panel_dist)
        return send_from_directory(admin_panel_dist, 'index.html')

    @app.errorhandler(404)
    def not_found(error):
        return "Not found", 404

    from app.endpoint.controllers import update_model
    with app.app_context():
        update_model()

    return app





