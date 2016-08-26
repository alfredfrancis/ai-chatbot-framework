from flask import Flask
from flask_cors import CORS

app = Flask(__name__)

# enable cross origin requests support
CORS(app)

import webServer.pages
import webServer.ui
import webServer.api
