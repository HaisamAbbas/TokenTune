from sqlalchemy.orm import Session

from app.models.evaluation import EvaluationDataset, EvaluationItem
from app.models.project import Project
from app.schemas.evaluation import EvaluationDatasetImport


def import_evaluation_dataset(
    db: Session, project: Project, payload: EvaluationDatasetImport
) -> tuple[EvaluationDataset, int]:
    """Create an EvaluationDataset and its EvaluationItem rows for `project`
    from an already-parsed import payload (see `EvaluationDatasetImport` -
    same shape as `examples/sample-rag-app/eval/dataset.json`)."""
    dataset = EvaluationDataset(
        project_id=project.id,
        name=payload.name,
        description=payload.description,
    )
    db.add(dataset)
    db.flush()

    for item in payload.items:
        db.add(
            EvaluationItem(
                dataset_id=dataset.id,
                question=item.question,
                expected_answer=item.expected_answer,
                source_doc=item.source_doc,
            )
        )

    db.commit()
    db.refresh(dataset)
    return dataset, len(payload.items)
