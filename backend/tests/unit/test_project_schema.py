import pytest
from pydantic import ValidationError

from app.schemas.project import ProjectCreate


def test_project_create_valid() -> None:
    project = ProjectCreate(name="RAG Demo", slug="rag-demo")
    assert project.slug == "rag-demo"


def test_project_create_requires_slug() -> None:
    with pytest.raises(ValidationError):
        ProjectCreate(name="RAG Demo")  # type: ignore[call-arg]
