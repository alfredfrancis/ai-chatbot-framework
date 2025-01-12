import logging
import os
from config import config

env = os.environ.get('APPLICATION_ENV', 'Development')
app_config = config[env]