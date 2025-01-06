from fastapi import APIRouter, HTTPException
from fastapi.responses import JSONResponse
from bson.objectid import ObjectId
from typing import List
from app.database import find_one, update_one
from app.train.schemas import TrainingData

router = APIRouter()

@router.post("/{story_id}/data")
async def save_training_data(story_id: str, training_data: TrainingData):
    """
    Save training data for given story
    """
    try:
        # Update the intent with new training data
        result = await update_one(
            "intents",
            {"_id": ObjectId(story_id)},
            {"trainingData": training_data.data}
        )
        
        if result == 0:
            raise HTTPException(status_code=404, detail="Story not found")
        
        return JSONResponse({"result": True})
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/{story_id}/data")
async def get_training_data(story_id: str):
    """
    Retrieve training data for a given story
    """
    try:
        # Get the intent
        intent = await find_one(
            "intents",
            {"_id": ObjectId(story_id)},
            projection={"trainingData": 1}
        )
        
        if not intent:
            raise HTTPException(status_code=404, detail="Story not found")
        
        return JSONResponse(content=intent.get("trainingData", []))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e)) 