from fastapi import APIRouter
from app.admin.entities import store
from app.admin.entities.schemas import Entity

router = APIRouter(prefix="/entities", tags=["entities"])


@router.post("/")
async def create_entity(entity: Entity):
    """Create a new entity"""
    entity_dict = entity.model_dump(exclude={"id"})
    entity = await store.add_entity(entity_dict)
    return entity


@router.get("/")
async def read_entities():
    """Get all entities"""
    return await store.list_entities()


@router.get("/{entity_id}")
async def read_entity(entity_id: str):
    """Get a specific entity by ID"""
    return await store.get_entity(entity_id)


@router.put("/{entity_id}")
async def update_entity(entity_id: str, entity: Entity):
    """Update an entity"""
    entity_dict = entity.model_dump(exclude={"id"})
    await store.edit_entity(entity_id, entity_dict)
    return {"status": "success"}


@router.delete("/{entity_id}")
async def delete_entity(entity_id: str):
    """Delete an entity"""
    await store.delete_entity(entity_id)
    return {"status": "success"}
