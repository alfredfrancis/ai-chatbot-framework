from fastapi import APIRouter, HTTPException, UploadFile, File
from fastapi.responses import JSONResponse, Response
from bson.json_util import dumps, loads
from typing import Dict, Any, Optional
from app.database import get_collection, find_one, update_one
import json

router = APIRouter(prefix="/agents")

@router.put("/{bot_name}/config")
async def set_config(bot_name: str, config: Dict[str, Any]):
    """
    Update bot config
    """
    bot = await find_one("bots", {"name": bot_name})
    if not bot:
        raise HTTPException(status_code=404, detail="Bot not found")
    
    result = await update_one("bots", {"name": bot_name}, {"config": config})
    return {"result": True}

@router.get("/{bot_name}/config")
async def get_config(bot_name: str):
    """
    Get bot config
    """
    bot = await find_one("bots", {"name": bot_name})
    if not bot:
        raise HTTPException(status_code=404, detail="Bot not found")
    return bot.get("config", {})

@router.get("/{bot_name}/export")
async def export_agent(bot_name: str):
    """
    Export all intents and entities for the bot as a JSON file
    """
    intents_collection = get_collection("intents")
    entities_collection = get_collection("entities")
    
    # Get all intents and entities
    intents = await intents_collection.find({"bot": bot_name}).to_list(None)
    entities = await entities_collection.find({"bot": bot_name}).to_list(None)
    
    export_data = {
        "intents": intents,
        "entities": entities
    }
    
    return Response(
        content=dumps(export_data),
        media_type='application/json',
        headers={'Content-Disposition': 'attachment;filename=chatbot_data.json'}
    )

@router.post("/{bot_name}/import")
async def import_agent(bot_name: str, file: UploadFile = File(...)):
    """
    Import intents and entities from a JSON file for the bot
    """
    if not file:
        raise HTTPException(status_code=400, detail="No file part")
    
    content = await file.read()
    json_data = json.loads(content)
    
    created_intents = []
    created_entities = []
    
    # Import intents
    if "intents" in json_data:
        intents_collection = get_collection("intents")
        for intent in json_data["intents"]:
            intent["bot"] = bot_name
            result = await intents_collection.insert_one(intent)
            if result.inserted_id:
                created_intents.append(str(result.inserted_id))
    
    # Import entities
    if "entities" in json_data:
        entities_collection = get_collection("entities")
        for entity in json_data["entities"]:
            entity["bot"] = bot_name
            result = await entities_collection.insert_one(entity)
            if result.inserted_id:
                created_entities.append(str(result.inserted_id))
    
    return {
        "num_intents_created": len(created_intents),
        "num_entities_created": len(created_entities)
    } 