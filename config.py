import os
from typing import Type

class BaseConfig(object):
    DEBUG = False
    Development = False
    MONGODB_HOST = "mongodb://127.0.0.1:27017/iky-ai"

    # Intent Classifier model details
    MODELS_DIR = "model_files/"
    INTENT_MODEL_NAME = "intent.model"
    DEFAULT_FALLBACK_INTENT_NAME = "fallback"
    DEFAULT_WELCOME_INTENT_NAME = "init_conversation"
    USE_WORD_VECTORS = True
    SPACY_LANG_MODEL = "en_core_web_md"

class DevelopmentConfig(BaseConfig):
    DEBUG = True
    Development = True
    TEMPLATES_AUTO_RELOAD=True

class TestingConfig(BaseConfig):
    DEBUG = True
    TESTING = True

class ProductionConfig(BaseConfig):
    # MongoDB Database Details
    MONGODB_HOST = "mongodb://mongodb:27017/iky-ai"

class HerokuConfig(ProductionConfig):
    MONGODB_HOST = os.environ.get('MONGO_URL')

class HelmConfig(ProductionConfig):
    MONGODB_HOST = os.environ.get('MONGO_URL')

config = {
    'Development': DevelopmentConfig,
    'Testing': TestingConfig,
    'Production': ProductionConfig,
    'Heroku': HerokuConfig,
    'Helm': HelmConfig
}