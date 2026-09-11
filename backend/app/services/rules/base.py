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

# Confidence-bucket thresholds for display (HIGH/MEDIUM/LOW), applied to the
# existing sample-size-only `scaled_confidence` float. Deliberately not a
# richer multi-factor formula yet - that needs historical data on whether
# "high confidence" recommendations actually held up after experiments ran,
# which doesn't exist yet. HIGH sits meaningfully above MIN_SAMPLE_SIZE
# rather than right at its edge.
CONFIDENCE_HIGH_THRESHOLD = 0.7
CONFIDENCE_MEDIUM_THRESHOLD = 0.35

# A completed experiment's quality_differences (candidate - baseline, one
# entry per metric the experiment's evaluator computed) must ALL be no worse
# than this to auto-mark a recommendation "validated" - a single passing
# metric must never hide a regression on another declared metric.
QUALITY_VALIDATION_THRESHOLD = -0.05

# The minimum share of traffic that must fall into the "simple" segment for
# a segmented-routing detection to be considered meaningful (see
# rule_e_segmented_routing.py) - below this, the split isn't worth acting on.
MIN_SEGMENT_SHARE = 0.10

# Number of days to project cost estimates over ("potential savings/month"),
# regardless of the actual analysis window length.
PROJECTION_DAYS = 30


def scaled_confidence(trace_count: int) -> float:
    """Confidence scales up from 0 (at the sample-size floor) towards 1.0 as
    trace_count grows to 4x the floor and beyond, capped at 1.0."""
    return min(1.0, trace_count / (MIN_SAMPLE_SIZE * 4))


def bucket_confidence(confidence: float) -> str:
    """Bucket a raw confidence float into a HIGH/MEDIUM/LOW label for
    display - see CONFIDENCE_HIGH_THRESHOLD/CONFIDENCE_MEDIUM_THRESHOLD."""
    if confidence >= CONFIDENCE_HIGH_THRESHOLD:
        return "high"
    if confidence >= CONFIDENCE_MEDIUM_THRESHOLD:
        return "medium"
    return "low"


def percentile(sorted_values: list[float], pct: float) -> float:
    """Nearest-rank percentile over an already-sorted list. Not a
    statistically rigorous interpolated percentile - good enough for an
    evidence-panel display, not for a formal significance test."""
    if not sorted_values:
        return 0.0
    idx = min(len(sorted_values) - 1, int(pct * len(sorted_values)))
    return sorted_values[idx]


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
    # V2 additions - all optional so existing call sites/tests that build a
    # WorkflowStats without them keep working unchanged.
    p95_input_tokens: float | None = None
    # Length of the analysis window in days, used to project avg_cost_per_trace
    # x trace_count into a "per PROJECTION_DAYS" estimate. Defaults to
    # PROJECTION_DAYS so an un-set window is a no-op multiplier of 1.
    window_days: float = PROJECTION_DAYS
    # Populated only for groups where segmentation was computed (see
    # rule_e_segmented_routing.py / services/analysis.py). Keys are "simple"
    # and "complex". None for rules that don't need segmentation.
    segments: dict[str, "WorkflowStats"] | None = None

    @property
    def estimated_monthly_cost(self) -> float:
        if self.window_days <= 0:
            return 0.0
        return self.avg_cost_per_trace * self.trace_count / self.window_days * PROJECTION_DAYS


WorkflowStats.model_rebuild()


def build_evidence(
    stats: WorkflowStats,
    *,
    current_value: Any = None,
    ratio: float | None = None,
    recommended_next_step: str,
    savings_fraction: float | None = None,
) -> dict[str, Any]:
    """Assemble the evidence-panel JSON shared across all rules. Rules
    without a numeric basis for a savings estimate (e.g. Rules C/D) pass
    savings_fraction=None - the panel then simply omits a $ range and leaves
    it to a future experiment to quantify."""
    monthly_cost = stats.estimated_monthly_cost
    evidence: dict[str, Any] = {
        "sample_size": stats.trace_count,
        "avg_input_tokens": round(stats.avg_input_tokens, 1),
        "p95_input_tokens": (
            round(stats.p95_input_tokens, 1) if stats.p95_input_tokens is not None else None
        ),
        "current_value": current_value,
        "ratio": round(ratio, 4) if ratio is not None else None,
        "estimated_monthly_cost": round(monthly_cost, 2),
        "quality_evidence": "not_yet_tested",
        "recommended_next_step": recommended_next_step,
    }
    if savings_fraction is not None:
        low = monthly_cost * savings_fraction * 0.8
        high = monthly_cost * savings_fraction * 1.2
        evidence["estimated_savings_low"] = round(low, 2)
        evidence["estimated_savings_high"] = round(high, 2)
    return evidence


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
    # V2: structured evidence panel (see build_evidence) and the estimated
    # dollar range derived from it - both optional so a rule that hasn't been
    # updated yet (or has no numeric basis) simply omits them.
    evidence: dict[str, Any] | None = None
    estimated_savings_low: float | None = None
    estimated_savings_high: float | None = None


class Rule(ABC):
    """A single optimization rule: inspects aggregated WorkflowStats for one
    (project_id, workflow, environment_id) group - already known to meet
    MIN_SAMPLE_SIZE - and optionally proposes a detection. Returns a schema
    object only - persistence is the caller's responsibility."""

    @abstractmethod
    def evaluate(self, stats: WorkflowStats) -> RuleDetection | None: ...
