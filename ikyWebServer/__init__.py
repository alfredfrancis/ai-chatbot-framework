from flask import Flask
from flask_cors import CORS, cross_origin

app = Flask(__name__)
CORS(app)

import ikyWebServer.home
import ikyWebServer.ui
import ikyWebServer.api
