import uuid
from abc import ABC, abstractmethod
from typing import Any

from pydantic import BaseModel

from app.schemas.optimization import RuleName

# Rules only fire once a workflow/environment group has accumulated at least
# this many traces in the analysis window - below this, stats are too noisy
# to act on. Enforced once, by RuleEngine.run(), before any rule's evaluate()
# is called - individual rules can assume they only ever see sufficient
# sample sizes.
MIN_SAMPLE_SIZE = 20


def scaled_confidence(trace_count: int) -> float:
    """Confidence scales up from 0 (at the sample-size floor) towards 1.0 as
    trace_count grows to 4x the floor and beyond, capped at 1.0."""
    return min(1.0, trace_count / (MIN_SAMPLE_SIZE * 4))


class WorkflowStats(BaseModel):
    sample_project_id: uuid.UUID
    workflow: str | None
    environment_id: uuid.UUID | None

    trace_count: int
    avg_input_tokens: float
    avg_output_tokens: float
    avg_retrieval_tokens: float | None = None
    avg_top_k: float | None = None
    avg_cost_per_trace: float
    model_usage: dict[str, int]
    avg_calls_per_trace: float


class RuleDetection(BaseModel):
    """What a single rule contributes: its detection logic and the proposed
    change. Everything that is the same for every rule - the
    project_id/workflow/environment_id passthrough and the confidence score -
    is stamped on by RuleEngine.run(), not by the rule itself."""

    rule_name: RuleName
    reason: str
    current_config: dict[str, Any]
    proposed_config: dict[str, Any]
    estimated_cost_impact: str
    required_experiment: dict[str, Any]


class Rule(ABC):
    """A single optimization rule: inspects aggregated WorkflowStats for one
    (project_id, workflow, environment_id) group - already known to meet
    MIN_SAMPLE_SIZE - and optionally proposes a detection. Returns a schema
    object only - persistence is the caller's responsibility."""

    @abstractmethod
    def evaluate(self, stats: WorkflowStats) -> RuleDetection | None: ...
