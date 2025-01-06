from motor.motor_asyncio import AsyncIOMotorClient, AsyncIOMotorDatabase
from typing import Optional

class Database:
    client: Optional[AsyncIOMotorClient] = None
    db: Optional[AsyncIOMotorDatabase] = None

    @classmethod
    def init_db(cls, mongodb_url: str):
        cls.client = AsyncIOMotorClient(mongodb_url)
        db_name = mongodb_url.split("/")[-1]
        cls.db = cls.client[db_name]
        return cls.db

    @classmethod
    def get_db(cls) -> AsyncIOMotorDatabase:
        return cls.db

    @classmethod
    async def close_db(cls):
        if cls.client is not None:
            cls.client.close()

# Database collections
def get_collection(collection_name: str):
    return Database.get_db()[collection_name]

# Utility functions for common database operations
async def insert_one(collection_name: str, document: dict):
    collection = get_collection(collection_name)
    result = await collection.insert_one(document)
    return result.inserted_id

async def find_one(collection_name: str, query: dict):
    collection = get_collection(collection_name)
    return await collection.find_one(query)

async def find_many(collection_name: str, query: dict, limit: int = 0):
    collection = get_collection(collection_name)
    cursor = collection.find(query)
    if limit > 0:
        cursor = cursor.limit(limit)
    return await cursor.to_list(None)

async def update_one(collection_name: str, query: dict, update: dict):
    collection = get_collection(collection_name)
    result = await collection.update_one(query, {"$set": update})
    return result.modified_count

async def delete_one(collection_name: str, query: dict):
    collection = get_collection(collection_name)
    result = await collection.delete_one(query)
    return result.deleted_count 