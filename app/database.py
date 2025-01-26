from typing import Annotated
from bson import ObjectId
from motor.motor_asyncio import AsyncIOMotorClient
from pydantic import PlainSerializer, PlainValidator
from app.config import app_config

ObjectIdField = Annotated[
    ObjectId,
    PlainSerializer(lambda x: str(x), return_type=str),
    PlainValidator(lambda x: ObjectId(x)),
]

client = AsyncIOMotorClient(app_config.MONGODB_HOST)
database = client.get_database(app_config.MONGODB_DATABASE)
