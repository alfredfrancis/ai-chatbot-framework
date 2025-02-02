from typing import Dict
from app.admin.bots.schemas import Bot, NLUConfiguration
from app.admin.entities.store import list_entities, bulk_import_entities
from app.admin.intents.store import list_intents, bulk_import_intents
from app.database import database
from datetime import datetime

bot_collection = database.get_collection("bot")


async def ensure_default_bot():
    # Check if the default bot exists
    default_bot = await bot_collection.find_one({"name": "default"})
    if default_bot is None:
        # Create the default bot
        default_bot_data = Bot(name="default")
        default_bot_data.created_at = datetime.utcnow()
        default_bot_data.updated_at = datetime.utcnow()
        await bot_collection.insert_one(
            default_bot_data.model_dump(exclude={"id": True})
        )
        return default_bot_data
    return Bot.model_validate(default_bot)


async def get_bot(name: str) -> Bot:
    bot = await bot_collection.find_one({"name": name})
    return Bot.model_validate(bot)


async def get_nlu_config(name: str) -> NLUConfiguration:
    bot = await get_bot(name)
    return bot.nlu_config


async def update_nlu_config(name: str, nlu_config: dict):
    await bot_collection.update_one(
        {"name": name}, {"$set": {"nlu_config": nlu_config}}
    )


async def export_bot(name) -> Dict:
    # Get all intents and entities
    intents = await list_intents()
    entities = await list_entities()

    entities = [entity.model_dump(exclude={"id"}) for entity in entities]
    intents = [
        intent.model_dump(exclude={"id": True, "parameters": {"__all__": {"id"}}})
        for intent in intents
    ]

    export_data = {"intents": intents, "entities": entities}
    return export_data


async def import_bot(name: str, data: Dict):
    intents = data.get("intents", [])
    entities = data.get("entities", [])

    created_intents = await bulk_import_intents(intents)
    created_entities = await bulk_import_entities(entities)

    return {
        "num_intents_created": len(created_intents),
        "num_entities_created": len(created_entities),
    }
