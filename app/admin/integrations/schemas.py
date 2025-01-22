from typing import Dict, Optional
from pydantic import BaseModel


class IntegrationBase(BaseModel):
    id: str
    name: str
    description: str
    status: bool = False
    settings: Optional[Dict] = {}


class IntegrationCreate(IntegrationBase):
    pass


class IntegrationUpdate(IntegrationBase):
    pass


class Integration(IntegrationBase):
    class Config:
        from_attributes = True
