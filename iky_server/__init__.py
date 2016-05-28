from flask import Flask
app = Flask(__name__)

import iky_server.intent_classifier
import iky_server.main
import iky_server.api
import iky_server.ner
import iky_server.mongo
