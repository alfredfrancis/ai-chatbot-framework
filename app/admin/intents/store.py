from typing import List, Dict
from bson import ObjectId
from app.admin.intents.schemas import Intent
from app.database import database

intent_collection = database.get_collection("intent")

async def add_intent(intent_data: dict) -> dict:
    result = await intent_collection.insert_one(intent_data)
    return await get_intent(str(result.inserted_id))

async def get_intent(id: str) -> Dict:
    intent = await intent_collection.find_one({"_id": ObjectId(id)})
    return Intent.model_validate(intent).model_dump()

async def list_intents() -> List[Dict]:
    intents = await intent_collection.find().to_list()
    return [Intent.model_validate(intent).model_dump() for intent in intents]

async def edit_intent(intent_id: str, intent_data: dict) -> dict:
    await intent_collection.update_one({"_id": ObjectId(intent_id)}, {"$set": intent_data})

async def delete_intent(intent_id: str):
    await intent_collection.delete_one({"_id": ObjectId(intent_id)}) 