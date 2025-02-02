from fastapi import APIRouter, UploadFile, File
from fastapi.responses import Response
from typing import Dict, Any
import json

from app.admin.bots import store

router = APIRouter(prefix="/bots", tags=["bots"])


@router.put("/{name}/config")
async def set_config(name: str, config: Dict[str, Any]):
    """
    Update bot config
    """
    await store.update_nlu_config(name, config)
    return {"message": "Config updated successfully"}


@router.get("/{name}/config")
async def get_config(name: str):
    """
    Get bot config
    """
    return await store.get_nlu_config(name)


@router.get("/{name}/export")
async def export_bot(name: str):
    """
    Export all intents and entities for the bot as a JSON file
    """
    data = await store.export_bot(name)
    return Response(
        content=json.dumps(data),
        media_type="application/json",
        headers={"Content-Disposition": "attachment;filename=chatbot_data.json"},
    )


@router.post("/{name}/import")
async def import_bot(name: str, file: UploadFile = File(...)):
    """
    Import intents and entities from a JSON file for the bot
    """

    content = await file.read()
    json_data = json.loads(content)

    return await store.import_bot(name, json_data)
