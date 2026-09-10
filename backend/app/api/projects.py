import uuid
from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.core.db import get_db
from app.models.project import Project
from app.schemas.project import ProjectCreate, ProjectRead
from app.schemas.telemetry import (
    CostBucket,
    GroupBy,
    TelemetryImportRequest,
    TelemetryImportResult,
)
from app.services.cost import aggregate_cost
from app.services.ingestion import import_telemetry

router = APIRouter(prefix="/projects", tags=["projects"])


@router.post("", response_model=ProjectRead, status_code=201)
def create_project(payload: ProjectCreate, db: Session = Depends(get_db)) -> Project:
    if db.query(Project).filter(Project.slug == payload.slug).first():
        raise HTTPException(status_code=409, detail="slug already exists")
    project = Project(
        name=payload.name,
        slug=payload.slug,
        langfuse_public_key=payload.langfuse_public_key,
        langfuse_secret_key=payload.langfuse_secret_key,
    )
    db.add(project)
    db.commit()
    db.refresh(project)
    return project


@router.get("", response_model=list[ProjectRead])
def list_projects(db: Session = Depends(get_db)) -> list[Project]:
    return db.query(Project).all()


@router.get("/{project_id}", response_model=ProjectRead)
def get_project(project_id: uuid.UUID, db: Session = Depends(get_db)) -> Project:
    project = db.get(Project, project_id)
    if project is None:
        raise HTTPException(status_code=404, detail="project not found")
    return project


def _get_project_or_404(project_id: uuid.UUID, db: Session) -> Project:
    project = db.get(Project, project_id)
    if project is None:
        raise HTTPException(status_code=404, detail="project not found")
    return project


@router.post("/{project_id}/telemetry/import", response_model=TelemetryImportResult)
def import_project_telemetry(
    project_id: uuid.UUID,
    payload: TelemetryImportRequest,
    db: Session = Depends(get_db),
) -> TelemetryImportResult:
    project = _get_project_or_404(project_id, db)
    result = import_telemetry(project, payload.from_ts, payload.to_ts, db)
    return TelemetryImportResult(
        traces_created=result.traces_created, llm_calls_created=result.llm_calls_created
    )


@router.get("/{project_id}/cost", response_model=list[CostBucket])
def get_project_cost(
    project_id: uuid.UUID,
    from_ts: datetime = Query(...),
    to_ts: datetime = Query(...),
    group_by: GroupBy | None = Query(None),
    db: Session = Depends(get_db),
) -> list[CostBucket]:
    _get_project_or_404(project_id, db)
    return aggregate_cost(db, project_id, from_ts, to_ts, group_by)
