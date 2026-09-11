import uuid
from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.core.db import get_db
from app.models.evaluation import EvaluationDataset
from app.models.experiment import Experiment, ExperimentRun
from app.models.optimization import OptimizationRecommendation
from app.models.project import Project
from app.schemas.evaluation import (
    EvaluationDatasetImport,
    EvaluationDatasetImportResult,
    EvaluationDatasetRead,
)
from app.schemas.experiment import (
    ExperimentComparisonResult,
    ExperimentCreate,
    ExperimentRead,
    ExperimentRunRead,
)
from app.schemas.optimization import (
    AnalyzeRequest,
    AnalyzeResult,
    OptimizationRecommendationRead,
    OptimizationRecommendationStatusUpdate,
)
from app.schemas.project import ProjectCreate, ProjectRead
from app.schemas.telemetry import (
    CostBucket,
    GroupBy,
    TelemetryImportRequest,
    TelemetryImportResult,
)
from app.services.analysis import run_analysis
from app.services.cost import aggregate_cost
from app.services.evaluation import import_evaluation_dataset
from app.services.experiments import create_experiment, run_experiment
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
        traces_created=result.traces_created,
        llm_calls_created=result.llm_calls_created,
        retrieval_steps_created=result.retrieval_steps_created,
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


@router.post("/{project_id}/optimizations/analyze", response_model=AnalyzeResult)
def analyze_project_optimizations(
    project_id: uuid.UUID,
    payload: AnalyzeRequest,
    db: Session = Depends(get_db),
) -> AnalyzeResult:
    project = _get_project_or_404(project_id, db)
    created = run_analysis(project, payload.from_ts, payload.to_ts, db)
    return AnalyzeResult(
        recommendations_created=len(created),
        recommendations=[OptimizationRecommendationRead.model_validate(row) for row in created],
    )


@router.get("/{project_id}/optimizations", response_model=list[OptimizationRecommendationRead])
def list_project_optimizations(
    project_id: uuid.UUID,
    status: str | None = Query(None),
    db: Session = Depends(get_db),
) -> list[OptimizationRecommendation]:
    _get_project_or_404(project_id, db)
    query = db.query(OptimizationRecommendation).filter(
        OptimizationRecommendation.project_id == project_id
    )
    if status is not None:
        query = query.filter(OptimizationRecommendation.status == status)
    return query.all()


def _get_recommendation_or_404(
    project_id: uuid.UUID, recommendation_id: uuid.UUID, db: Session
) -> OptimizationRecommendation:
    recommendation = (
        db.query(OptimizationRecommendation)
        .filter(
            OptimizationRecommendation.id == recommendation_id,
            OptimizationRecommendation.project_id == project_id,
        )
        .first()
    )
    if recommendation is None:
        raise HTTPException(status_code=404, detail="recommendation not found")
    return recommendation


@router.patch(
    "/{project_id}/optimizations/{recommendation_id}",
    response_model=OptimizationRecommendationRead,
)
def update_optimization_status(
    project_id: uuid.UUID,
    recommendation_id: uuid.UUID,
    payload: OptimizationRecommendationStatusUpdate,
    db: Session = Depends(get_db),
) -> OptimizationRecommendation:
    _get_project_or_404(project_id, db)
    recommendation = _get_recommendation_or_404(project_id, recommendation_id, db)

    if payload.status == "adopted":
        experiment = (
            db.get(Experiment, recommendation.experiment_id)
            if recommendation.experiment_id
            else None
        )
        if experiment is None or experiment.status != "completed":
            raise HTTPException(
                status_code=409,
                detail=("cannot adopt a recommendation without a completed linked experiment"),
            )

    recommendation.status = payload.status
    db.commit()
    db.refresh(recommendation)
    return recommendation


@router.post(
    "/{project_id}/evaluations/import",
    response_model=EvaluationDatasetImportResult,
    status_code=201,
)
def import_project_evaluation_dataset(
    project_id: uuid.UUID,
    payload: EvaluationDatasetImport,
    db: Session = Depends(get_db),
) -> EvaluationDatasetImportResult:
    project = _get_project_or_404(project_id, db)
    dataset, items_created = import_evaluation_dataset(db, project, payload)
    return EvaluationDatasetImportResult(
        dataset=EvaluationDatasetRead.model_validate(dataset), items_created=items_created
    )


@router.get("/{project_id}/evaluations", response_model=list[EvaluationDatasetRead])
def list_project_evaluations(
    project_id: uuid.UUID, db: Session = Depends(get_db)
) -> list[EvaluationDataset]:
    _get_project_or_404(project_id, db)
    return db.query(EvaluationDataset).filter(EvaluationDataset.project_id == project_id).all()


def _get_experiment_or_404(
    project_id: uuid.UUID, experiment_id: uuid.UUID, db: Session
) -> Experiment:
    experiment = (
        db.query(Experiment)
        .filter(Experiment.id == experiment_id, Experiment.project_id == project_id)
        .first()
    )
    if experiment is None:
        raise HTTPException(status_code=404, detail="experiment not found")
    return experiment


@router.post("/{project_id}/experiments", response_model=ExperimentRead, status_code=201)
def create_project_experiment(
    project_id: uuid.UUID,
    payload: ExperimentCreate,
    db: Session = Depends(get_db),
) -> Experiment:
    project = _get_project_or_404(project_id, db)

    dataset = db.get(EvaluationDataset, payload.evaluation_dataset_id)
    if dataset is None or dataset.project_id != project_id:
        raise HTTPException(status_code=404, detail="evaluation dataset not found")

    recommendation = None
    if payload.recommendation_id is not None:
        recommendation = _get_recommendation_or_404(project_id, payload.recommendation_id, db)

    return create_experiment(
        db=db,
        project=project,
        baseline_config=payload.baseline_config,
        experiment_config=payload.experiment_config,
        evaluation_dataset=dataset,
        name=payload.name,
        recommendation=recommendation,
    )


@router.post(
    "/{project_id}/experiments/{experiment_id}/run",
    response_model=ExperimentComparisonResult,
)
async def run_project_experiment(
    project_id: uuid.UUID,
    experiment_id: uuid.UUID,
    db: Session = Depends(get_db),
) -> ExperimentComparisonResult:
    _get_project_or_404(project_id, db)
    experiment = _get_experiment_or_404(project_id, experiment_id, db)

    try:
        outcome = await run_experiment(db, experiment)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from None

    if outcome.experiment.status == "failed":
        # A variant fully failed (e.g. every item errored) - the comparison
        # numbers were never computed (see run_experiment), so surface the
        # failure rather than returning 200 with fabricated percentages.
        raise HTTPException(status_code=422, detail=outcome.experiment.error)

    # run_experiment only omits the comparison fields (leaves them None) when
    # experiment.status == "failed", which we've just ruled out above.
    assert outcome.cost_reduction_pct is not None
    assert outcome.quality_difference is not None
    assert outcome.latency_difference_ms is not None
    assert outcome.token_reduction_pct is not None

    return ExperimentComparisonResult(
        experiment=ExperimentRead.model_validate(outcome.experiment),
        baseline_run=ExperimentRunRead.model_validate(outcome.baseline_run),
        experiment_run=ExperimentRunRead.model_validate(outcome.experiment_run),
        cost_reduction_pct=outcome.cost_reduction_pct,
        quality_difference=outcome.quality_difference,
        latency_difference_ms=outcome.latency_difference_ms,
        token_reduction_pct=outcome.token_reduction_pct,
        failed_questions=outcome.failed_questions,
    )


@router.get("/{project_id}/experiments", response_model=list[ExperimentRead])
def list_project_experiments(
    project_id: uuid.UUID, db: Session = Depends(get_db)
) -> list[Experiment]:
    _get_project_or_404(project_id, db)
    return db.query(Experiment).filter(Experiment.project_id == project_id).all()


@router.get("/{project_id}/experiments/{experiment_id}", response_model=ExperimentRead)
def get_project_experiment(
    project_id: uuid.UUID, experiment_id: uuid.UUID, db: Session = Depends(get_db)
) -> Experiment:
    _get_project_or_404(project_id, db)
    return _get_experiment_or_404(project_id, experiment_id, db)


@router.get(
    "/{project_id}/experiments/{experiment_id}/runs",
    response_model=list[ExperimentRunRead],
)
def list_project_experiment_runs(
    project_id: uuid.UUID, experiment_id: uuid.UUID, db: Session = Depends(get_db)
) -> list[ExperimentRun]:
    _get_project_or_404(project_id, db)
    experiment = _get_experiment_or_404(project_id, experiment_id, db)
    return db.query(ExperimentRun).filter(ExperimentRun.experiment_id == experiment.id).all()
