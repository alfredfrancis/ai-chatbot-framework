from typing import List, Dict

from bson import ObjectId

from app.admin.entities.schemas import Entity
from app.database import database

entity_collection = database.get_collection("entity")

async def add_entity(entity_data: dict) -> Entity:
    result = await entity_collection.insert_one(entity_data)
    return await get_entity(str(result.inserted_id))

async def get_entity(id: str) -> Entity:
    entity = await entity_collection.find_one({"_id": ObjectId(id)})
    return Entity.model_validate(entity)

async def list_entities() -> List[Entity]:
    entities = await entity_collection.find().to_list()
    return [Entity.model_validate(entity) for entity in entities]

async def edit_entity(entity_id: str, entity_data: dict) -> dict:
    await entity_collection.update_one({"_id": ObjectId(entity_id)}, {"$set": entity_data})

async def delete_entity(entity_id: str):
    await entity_collection.delete_one({"_id": ObjectId(entity_id)})

