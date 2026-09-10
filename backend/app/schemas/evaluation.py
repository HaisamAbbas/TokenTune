import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict


class EvaluationItemImport(BaseModel):
    question: str
    expected_answer: str
    source_doc: str | None = None


class EvaluationDatasetImport(BaseModel):
    """Body for importing an evaluation dataset, matching the shape of
    `examples/sample-rag-app/eval/dataset.json` (its `description` maps to
    this dataset's `description`, its `items` map to `EvaluationItem` rows)."""

    name: str
    description: str | None = None
    items: list[EvaluationItemImport]


class EvaluationItemRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    dataset_id: uuid.UUID
    question: str
    expected_answer: str
    source_doc: str | None
    created_at: datetime


class EvaluationDatasetRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    project_id: uuid.UUID
    name: str
    description: str | None
    created_at: datetime


class EvaluationDatasetImportResult(BaseModel):
    dataset: EvaluationDatasetRead
    items_created: int
