from fastapi import APIRouter, HTTPException, BackgroundTasks
from fastapi.responses import JSONResponse
from app.nlu.training import train_models

router = APIRouter()

@router.post("/build_models")
async def build_models(background_tasks: BackgroundTasks):
    """
    Build Intent classification and NER Models
    """
    try:
        # Run training in background to avoid blocking
        background_tasks.add_task(train_models)
        return JSONResponse({"result": True})
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Error building models: {str(e)}"
        )