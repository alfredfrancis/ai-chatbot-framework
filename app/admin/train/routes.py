from fastapi import APIRouter, HTTPException, BackgroundTasks
from app.admin.intents import store
from app.dependencies import reload_dialogue_manager
from app.bot.nlu.pipeline_utils import train_pipeline

router = APIRouter(prefix="/train", tags=["train"])


@router.post("/{intent_id}/data")
async def save_training_data(intent_id: str, training_data: list[dict]):
    """
    Save training data for a given story
    """
    intent = await store.get_intent(
        intent_id
    )  # Assuming story_id corresponds to an intent
    if not intent:
        raise HTTPException(status_code=404, detail="Story not found")

    intent.trainingData = training_data
    await store.edit_intent(
        intent_id, intent.model_dump()
    )  # Update the intent with training data
    return {"status": "success"}


@router.get("/{intent_id}/data")
async def get_training_data(intent_id: str):
    """
    Retrieve training data for a given story
    """
    intent = await store.get_intent(
        intent_id
    )  # Assuming story_id corresponds to an intent
    if not intent:
        raise HTTPException(status_code=404, detail="Story not found")

    return intent.trainingData


@router.post("/build_models")
async def build_models(background_tasks: BackgroundTasks):
    """
    Build Intent classification and NER Models
    """
    background_tasks.add_task(build_models_background)
    return {"status": "training started in the background"}


async def build_models_background():
    """
    Build Intent classification and NER Models
    """
    await train_pipeline()
    await reload_dialogue_manager()
