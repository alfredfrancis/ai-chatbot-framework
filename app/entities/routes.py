from fastapi import APIRouter, HTTPException
from fastapi.responses import JSONResponse
from bson.objectid import ObjectId
from bson.json_util import dumps, loads
from typing import List
from app.database import get_collection, find_one, find_many, insert_one, update_one, delete_one
from app.entities.schemas import EntityCreate, EntityUpdate, EntityInDB

router = APIRouter()

@router.post("/")
async def create_entity(entity: EntityCreate):
    """Create a new entity"""
    try:
        # Convert Pydantic model to dict
        entity_dict = entity.dict(exclude_unset=True)
        entity_dict["entityValues"] = []  # Initialize empty values
        
        # Insert into database
        result = await insert_one("entities", entity_dict)
        
        return JSONResponse({"_id": str(result)})
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/")
async def read_entities():
    """Get all entities (name and id only)"""
    try:
        entities = await find_many(
            "entities",
            {},
            projection={"name": 1, "_id": 1}
        )
        return JSONResponse(content=loads(dumps(entities)))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/{entity_id}")
async def read_entity(entity_id: str):
    """Get a specific entity by ID"""
    try:
        entity = await find_one("entities", {"_id": ObjectId(entity_id)})
        if not entity:
            raise HTTPException(status_code=404, detail="Entity not found")
        return JSONResponse(content=loads(dumps(entity)))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.put("/{entity_id}")
async def update_entity(entity_id: str, entity: EntityUpdate):
    """Update an entity"""
    try:
        # Convert Pydantic model to dict
        entity_dict = entity.dict(exclude_unset=True)
        
        # Update in database
        result = await update_one(
            "entities",
            {"_id": ObjectId(entity_id)},
            entity_dict
        )
        
        if result == 0:
            raise HTTPException(status_code=404, detail="Entity not found")
        
        return JSONResponse({"result": True})
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.delete("/{entity_id}")
async def delete_entity(entity_id: str):
    """Delete an entity"""
    try:
        result = await delete_one("entities", {"_id": ObjectId(entity_id)})
        
        if result == 0:
            raise HTTPException(status_code=404, detail="Entity not found")
        
        return JSONResponse({"result": True})
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e)) 