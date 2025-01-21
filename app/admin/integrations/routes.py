from typing import List
from fastapi import APIRouter, HTTPException
from . import store
from .schemas import Integration, IntegrationUpdate

router = APIRouter(prefix="/integrations", tags=["integrations"])


@router.get("/", response_model=List[Integration])
async def list_integrations():
    """List all available integrations."""
    return await store.list_integrations()


@router.get("/{integration_name}", response_model=Integration)
async def get_integration(integration_name: str):
    """Get a specific integration by name."""
    integration = await store.get_integration(integration_name)
    if not integration:
        raise HTTPException(status_code=404, detail="Integration not found")
    return integration


@router.put("/{integration_name}", response_model=Integration)
async def update_integration(integration_name: str, integration: IntegrationUpdate):
    """Update an integration's status and settings."""
    updated_integration = await store.update_integration(integration_name, integration)
    if not updated_integration:
        raise HTTPException(status_code=404, detail="Integration not found")
    return updated_integration
