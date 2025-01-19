from typing import List, Dict
from bson import ObjectId
from app.admin.intents.schemas import Intent
from app.database import database

intent_collection = database.get_collection("intent")


async def add_intent(intent_data: dict) -> Intent:
    result = await intent_collection.insert_one(intent_data)
    return await get_intent(str(result.inserted_id))


async def get_intent(id: str) -> Intent:
    intent = await intent_collection.find_one({"_id": ObjectId(id)})
    return Intent.model_validate(intent)


async def list_intents() -> List[Intent]:
    intents = await intent_collection.find().to_list()
    return [Intent.model_validate(intent) for intent in intents]


async def edit_intent(intent_id: str, intent_data: dict):
    await intent_collection.update_one(
        {"_id": ObjectId(intent_id)}, {"$set": intent_data}
    )


async def delete_intent(intent_id: str):
    await intent_collection.delete_one({"_id": ObjectId(intent_id)})


async def bulk_import_intents(intents: List[Dict]) -> List[str]:
    created_intents = []
    if intents:
        for intent in intents:
            result = await intent_collection.update_one(
                {"name": intent.get("name")}, {"$set": intent}, upsert=True
            )
            if result.upserted_id:
                created_intents.append(str(result.upserted_id))
    return created_intents
