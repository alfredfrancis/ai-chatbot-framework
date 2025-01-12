import os
import dotenv
from pydantic import BaseModel

dotenv.load_dotenv()

class BaseConfig(BaseModel):
    DEBUG: bool = False
    Development: bool = False
    MONGODB_HOST: str = "mongodb://127.0.0.1:27017/iky-ai"

    # Intent Classifier model details
    MODELS_DIR: str = "model_files/"
    INTENT_MODEL_NAME: str = "intent.model"
    DEFAULT_FALLBACK_INTENT_NAME: str = "fallback"
    DEFAULT_WELCOME_INTENT_NAME: str = "init_conversation"
    USE_WORD_VECTORS: bool = True
    SPACY_LANG_MODEL: str = "en_core_web_md"

class DevelopmentConfig(BaseConfig):
    DEBUG: bool = True
    Development: bool = True
    TEMPLATES_AUTO_RELOAD: bool = True

class TestingConfig(BaseConfig):
    DEBUG: bool = True
    TESTING: bool = True

class ProductionConfig(BaseConfig):
    # MongoDB Database Details
    MONGODB_HOST: str = "mongodb://mongodb:27017/iky-ai"

config = {
    'Development': DevelopmentConfig,
    'Testing': TestingConfig,
    'Production': ProductionConfig,
}

def from_envvar():
    """Get configuration class from environment variable."""
    choice = os.environ.get('APPLICATION_ENV', 'Development')
    if choice not in config:
        msg = "APPLICATION_ENV={} is not valid, must be one of {}".format(choice, set(config))
        raise ValueError(msg)
    loaded_config = config[choice](**os.environ)
    return loaded_config