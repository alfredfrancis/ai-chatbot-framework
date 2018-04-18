import os
from flask import Flask
from flask_cors import CORS

app = Flask(__name__)

cors = CORS(app)

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
    TEMPLATES_AUTO_RELOAD=True
)


from flask_mongoengine import MongoEngine
db = MongoEngine(app)

from blinker import Namespace
my_signals = Namespace()

@app.errorhandler(404)
def not_found(error):
    return "Not found", 404


from app.nlu.controllers import nlu
from app.intents.controllers import intents
from app.train.controllers import train
from app.endpoint.controllers import endpoint

app.register_blueprint(nlu)
app.register_blueprint(intents)
app.register_blueprint(train)
app.register_blueprint(endpoint)
