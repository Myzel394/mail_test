import uuid
from datetime import datetime

from pydantic import BaseModel, Field

from app import constants, life_constants
from app.models.enums.api_key import APIKeyScope

__all__ = [
    "APIKeyCreateModel",
    "APIKeyCreatedResponseModel",
    "APIKeyDeleteModel",
    "APIKeyResponseModel",
]


class APIKeyCreateModel(BaseModel):
    expires_at: datetime = Field(
        default_factory=lambda: datetime.utcnow() + constants.DEFAULT_API_EXPIRE_DURATION
    )
    scopes: list[APIKeyScope]
    label: str = Field(
        ...,
        max_length=constants.API_KEY_MAX_LABEL_LENGTH,
    )


class APIKeyResponseModel(BaseModel):
    id: uuid.UUID
    expires_at: datetime
    scopes: list[APIKeyScope]
    label: str

    class Config:
        orm_mode = True


class APIKeyCreatedResponseModel(APIKeyResponseModel):
    key: str


class APIKeyDeleteModel(BaseModel):
    key: str = Field(
        ...,
        min_length=life_constants.API_KEY_LENGTH,
        max_length=life_constants.API_KEY_LENGTH,
    )
