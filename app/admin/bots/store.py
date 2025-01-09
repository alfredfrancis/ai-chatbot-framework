from typing import Dict
from app.admin.bots.schemas import Bot
from app.admin.entities.store import list_entities
from app.admin.intents.store import list_intents
from app.database import database

bot_collection = database.get_collection("bot")
intent_collection = database.get_collection("intent")
entity_collection = database.get_collection("entity")

async def add_bot(data: dict):
    return await bot_collection.insert_one(data)

async def get_bot(name: str)-> Bot:
    bot = await bot_collection.find_one({"name": name})
    return Bot.model_validate(bot)

async def get_config(name: str) -> Dict:
    bot = await get_bot(name)
    return bot.config

async def update_config(name: str, entity_data: dict) -> dict:
    await bot_collection.update_one({"name": name}, {"$set": {"config": entity_data}})

async def export_bot(name) -> Dict:
    # Get all intents and entities
    intents = await list_intents()
    entities = await list_entities()

    entities = [entity.model_dump(exclude={"id"}) for entity in entities]
    intents = [intent.model_dump(exclude={"id"})  for intent in intents]

    export_data = {
        "intents": intents,
        "entities": entities
    }
    return export_data

async def import_bot(name: str, data: Dict):
    intents = data.get("intents",[])
    entities = data.get("entities",[])

    created_intents = []
    created_entities = []

    # Import intents
    if intents:
        for intent in intents:
            result = await intent_collection.update_one({"name": intent.get("name")}, {"$set": intent},upsert=True)
            print(result)
            if result.upserted_id:
                created_intents.append(str(result.upserted_id))

    # Import entities
    if entities:
        for entity in entities:
            result = await entity_collection.update_one({"name": entity.get("name")}, {"$set": entity},upsert=True)
            print(result)
            if result.upserted_id:
                created_entities.append(str(result.upserted_id))

    return {
        "num_intents_created": len(created_intents),
        "num_entities_created": len(created_entities)
    }

