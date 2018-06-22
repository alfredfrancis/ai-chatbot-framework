import os

from blinker import Namespace
from flask import Flask
from flask_cors import CORS
from flask_mongoengine import MongoEngine

app = Flask(__name__)

CORS(app)

# Configurations
try:
    env = os.environ['APPLICATION_ENV']
except KeyError as e:
    # logging.error('Unknown environment key, defaulting to Development')
    env = 'Development'

app.config.from_object('config.%s' % env)
app.config.update(
    DEBUG=True,
    TESTING=True,
    TEMPLATES_AUTO_RELOAD=True)

db = MongoEngine(app)

my_signals = Namespace()

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


@app.errorhandler(404)
def not_found(error):
    return "Not found", 404
