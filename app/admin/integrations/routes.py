from typing import List
from fastapi import APIRouter, HTTPException
from . import store
from .schemas import Integration, IntegrationUpdate

router = APIRouter(prefix="/integrations", tags=["integrations"])


@router.get("/", response_model=List[Integration])
async def list_integrations():
    """List all available integrations."""
    return await store.list_integrations()


@router.get("/{id}", response_model=Integration)
async def get_integration(id: str):
    """Get a specific integration by ID."""
    integration = await store.get_integration(id)
    if not integration:
        raise HTTPException(status_code=404, detail="Integration not found")
    return integration


@router.put("/{id}", response_model=Integration)
async def update_integration(id: str, integration: IntegrationUpdate):
    """Update an integration's status and settings."""
    updated_integration = await store.update_integration(id, integration)
    if not updated_integration:
        raise HTTPException(status_code=404, detail="Integration not found")
    return updated_integration
