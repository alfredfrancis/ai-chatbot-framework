class Config(object):
    DEBUG = False
    MONGODB_DB = "iky-ai"
    MONGODB_HOST = "127.0.0.1"
    MONGODB_PORT = 27017
    MONGODB_USERNAME = ""
    MONGODB_USERNAME = ""

    # Intent Classifier model details
    MODELS_DIR = "model_files/"
    INTENT_MODEL_NAME = "intent.model"
    DEFAULT_FALLBACK_INTENT_NAME = "fallback"
    DEFAULT_WELCOME_INTENT_NAME = "init_conversation"
    USE_WORD_VECTORS = True


class Development(Config):
    DEBUG = True


class Production(Config):
    # MongoDB Database Details
    MONGODB_DB = "iky-ai"
    MONGODB_HOST = "mongodb"
    MONGODB_PORT = 27017
    MONGODB_USERNAME = ""
    MONGODB_USERNAME = ""

    # Web Server details
    WEB_SERVER_PORT = 8001
