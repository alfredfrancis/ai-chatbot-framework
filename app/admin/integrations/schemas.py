from typing import Dict, Optional
from pydantic import BaseModel


class IntegrationBase(BaseModel):
    status: bool = False
    settings: Optional[Dict] = {}


class IntegrationCreate(IntegrationBase):
    pass


class IntegrationUpdate(IntegrationBase):
    pass


class Integration(IntegrationBase):
    integration_name: str

    class Config:
        from_attributes = True
