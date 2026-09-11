from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.core.db import get_db
from app.models.project import Project
from app.schemas.telemetry import TelemetryReportRequest, TelemetryReportResult
from app.services.ingestion import report_telemetry

# Endpoints called by the TokenTune SDK itself (as opposed to the dashboard
# frontend) - kept separate from app.api.projects because the SDK only ever
# knows a project's slug, never its backend UUID, so these routes take the
# slug in the request body rather than a UUID path segment.
router = APIRouter(prefix="/sdk", tags=["sdk"])


@router.post("/telemetry/report", response_model=TelemetryReportResult)
def report_sdk_telemetry(
    payload: TelemetryReportRequest, db: Session = Depends(get_db)
) -> TelemetryReportResult:
    project = db.query(Project).filter(Project.slug == payload.project_slug).first()
    if project is None:
        raise HTTPException(status_code=404, detail="project not found")

    result = report_telemetry(project, payload.items, db)
    return TelemetryReportResult(
        traces_created=result.traces_created, llm_calls_created=result.llm_calls_created
    )
