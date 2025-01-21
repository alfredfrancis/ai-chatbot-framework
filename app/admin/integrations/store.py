from typing import List, Optional
from app.database import database
from .schemas import Integration, IntegrationUpdate

collection_name = "integrations"


async def list_integrations() -> List[Integration]:
    """Get all integrations."""
    cursor = database[collection_name].find()
    integrations = await cursor.to_list(length=None)
    return [Integration(**integration) for integration in integrations]


async def get_integration(integration_name: str) -> Optional[Integration]:
    """Get a specific integration by name."""
    integration = await database[collection_name].find_one(
        {"integration_name": integration_name}
    )
    if integration:
        return Integration(**integration)
    return None


async def update_integration(
    integration_name: str, integration: IntegrationUpdate
) -> Optional[Integration]:
    """Update an integration's status and settings."""
    update_data = integration.model_dump(exclude_unset=True)

    result = await database[collection_name].find_one_and_update(
        {"integration_name": integration_name},
        {"$set": update_data},
        return_document=True,
    )

    if result:
        return Integration(**result)
    return None


async def ensure_default_integrations():
    """Ensure default integrations exist in the database."""
    default_integrations = [
        {
            "integration_name": "facebook",
            "status": False,
            "settings": {
                "verify": "ai-chatbot-framework",
                "secret": "",
                "page_access_token": "",
            },
        },
        {"integration_name": "chat_widget", "status": True, "settings": {}},
    ]

    for integration in default_integrations:
        await database[collection_name].update_one(
            {"integration_name": integration["integration_name"]},
            {"$setOnInsert": integration},
            upsert=True,
        )
