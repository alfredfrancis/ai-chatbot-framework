from flask import Flask

app = Flask(__name__)

import iky_server.main
import iky_server.crf_train
import iky_server.predict
import iky_server.nlp
import iky_server.ui
import iky_server.api
