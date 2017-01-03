class Config(object):
    DEBUG = False
    DB_NAME = "iky-ai"
    DB_HOST = "mongodb://127.0.0.1:27017/"
    DB_USERNAME = ""
    DB_PASSWORD = ""

    # Web Server details
    WEB_SERVER_PORT = 8080

    # Intent Classifier model detials
    MODELS_DIR = "model_files"
    INTENT_MODEL_NAME = "intent.model"
    DEFAULT_FALLBACK_INTENT_NAME = "fallback"

class Production(Config):
    # MongoDB Database Details
    DB_HOST = "mongodb://127.0.0.1:27017/"
    DB_USERNAME = ""
    DB_PASSWORD = ""

    # Web Server details
    WEB_SERVER_PORT = 80

class Development(Config):
    DEBUG = True
