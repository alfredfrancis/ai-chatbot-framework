from flask import Flask, render_template

app = Flask(__name__)

# Configurations
app.config.from_object('config')

@app.errorhandler(404)
def not_found(error):
    return render_template('404.html'), 404

from app.core.controllers import core as core
from app.stories.controllers import stories as stories
from app.train.controllers import train as train
from app.endpoint.controllers import endpoint as endpoint

app.register_blueprint(core)
app.register_blueprint(stories)
app.register_blueprint(train)
app.register_blueprint(endpoint)