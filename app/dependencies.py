from typing import Optional
from app.bot.dialogue_manager.dialogue_manager import DialogueManager
from app.config import app_config
import logging

logger = logging.getLogger(__name__)

_dialogue_manager: Optional[DialogueManager] = None


async def get_dialogue_manager():
    global _dialogue_manager
    return _dialogue_manager


async def set_dialogue_manager(dialogue_manager: DialogueManager):
    global _dialogue_manager
    _dialogue_manager = dialogue_manager


async def init_dialogue_manager():
    global _dialogue_manager
    logger.info("initializing dialogue manager")
    _dialogue_manager = await DialogueManager.from_config()
    _dialogue_manager.update_model(app_config.MODELS_DIR)
    logger.info("dialogue manager initialized")


async def reload_dialogue_manager():
    """
    Reload the global dialogue manager object with new data and models
    """

    # recreate dialogue manager with new data
    dialogue_manager = await DialogueManager.from_config()

    # update dialogue manager with new models
    dialogue_manager.update_model(app_config.MODELS_DIR)

    await set_dialogue_manager(dialogue_manager)

    logger.info("dialogue manager reloaded")
