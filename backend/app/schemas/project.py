import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict


class ProjectCreate(BaseModel):
    name: str
    slug: str
    langfuse_public_key: str | None = None
    langfuse_secret_key: str | None = None


class ProjectUpdate(BaseModel):
    """All fields optional and unset-by-default: only fields actually
    present in the request body are changed (see the endpoint's use of
    `model_dump(exclude_unset=True)`) - omitting a key leaves it as-is,
    it does not clear it. Pass an empty string to explicitly clear a key."""

    name: str | None = None
    langfuse_public_key: str | None = None
    langfuse_secret_key: str | None = None


class ProjectRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    name: str
    slug: str
    created_at: datetime
    langfuse_configured: bool


class EnvironmentRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    project_id: uuid.UUID
    name: str
    created_at: datetime
