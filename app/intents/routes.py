import os
from fastapi import APIRouter, HTTPException
from fastapi.responses import JSONResponse
from bson.objectid import ObjectId
from bson.json_util import dumps, loads
from typing import List
from app.database import get_collection, find_one, find_many, insert_one, update_one, delete_one
from app.intents.schemas import IntentCreate, IntentUpdate, IntentInDB
from app.nlu.training import train_models

router = APIRouter()

@router.post("/")
async def create_intent(intent: IntentCreate):
    """Create a new intent"""
    try:
        # Convert Pydantic model to dict
        intent_dict = intent.dict(exclude_unset=True)
        intent_dict["trainingData"] = []
        intent_dict["labeledSentences"] = []
        
        # Insert into database
        result = await insert_one("intents", intent_dict)
        
        return JSONResponse({"_id": str(result)})
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/")
async def read_intents():
    """Get all intents"""
    intents = await find_many("intents", {})
    return JSONResponse(content=loads(dumps(intents)))

@router.get("/{intent_id}")
async def read_intent(intent_id: str):
    """Get a specific intent by ID"""
    try:
        intent = await find_one("intents", {"_id": ObjectId(intent_id)})
        if not intent:
            raise HTTPException(status_code=404, detail="Intent not found")
        return JSONResponse(content=loads(dumps(intent)))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.put("/{intent_id}")
async def update_intent(intent_id: str, intent: IntentUpdate):
    """Update an intent"""
    try:
        # Convert Pydantic model to dict
        intent_dict = intent.dict(exclude_unset=True)
        
        # Update in database
        result = await update_one(
            "intents",
            {"_id": ObjectId(intent_id)},
            intent_dict
        )
        
        if result == 0:
            raise HTTPException(status_code=404, detail="Intent not found")
        
        return JSONResponse({"result": True})
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.delete("/{intent_id}")
async def delete_intent(intent_id: str):
    """Delete an intent"""
    try:
        # Delete from database
        result = await delete_one("intents", {"_id": ObjectId(intent_id)})
        
        if result == 0:
            raise HTTPException(status_code=404, detail="Intent not found")
        
        # Retrain models
        try:
            await train_models()
        except Exception:
            pass  # Continue even if training fails
        
        # Remove NER model file
        try:
            model_path = f"model_files/{intent_id}.model"
            if os.path.exists(model_path):
                os.remove(model_path)
        except OSError:
            pass  # Continue even if file removal fails
        
        return JSONResponse({"result": True})
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e)) 