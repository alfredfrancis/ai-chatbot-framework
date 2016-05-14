from flask import Flask
app = Flask(__name__)

import iky_server.functions
import iky_server.main
import iky_server.api
#mport iky_server.wit