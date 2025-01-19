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


async def edit_entity(entity_id: str, entity_data: dict):
    await entity_collection.update_one(
        {"_id": ObjectId(entity_id)}, {"$set": entity_data}
    )


async def delete_entity(entity_id: str):
    await entity_collection.delete_one({"_id": ObjectId(entity_id)})


async def list_synonyms():
    """list all synonyms across the entities"""
    synonyms = {}

    entities = await list_entities()
    for entity in entities:
        for value in entity.entity_values:
            for synonym in value.synonyms:
                synonyms[synonym] = value.value
    return synonyms


async def bulk_import_entities(entities: List[Dict]) -> List[str]:
    created_entities = []
    if entities:
        for entity in entities:
            result = await entity_collection.update_one(
                {"name": entity.get("name")}, {"$set": entity}, upsert=True
            )
            if result.upserted_id:
                created_entities.append(str(result.upserted_id))
    return created_entities
