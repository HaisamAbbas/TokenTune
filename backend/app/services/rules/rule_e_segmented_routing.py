from app.services.pricing import estimate_cost, get_pricing_table
from app.services.rules.base import MIN_SEGMENT_SHARE, Rule, RuleDetection, WorkflowStats, build_evidence

REQUIRED_PRICING_KEYS = ("input_per_1k", "output_per_1k")


class SegmentedModelRoutingRule(Rule):
    """Unlike Rule B (which recommends switching an entire workflow to a
    cheaper model), this rule only fires when the workflow's traces split
    into a meaningful "simple" vs "complex" segment (see
    services/analysis.py's segmentation helper) - and only recommends
    routing the simple segment to a cheaper model, leaving complex traffic on
    the current model untouched."""

    def evaluate(self, stats: WorkflowStats) -> RuleDetection | None:
        if not stats.segments:
            return None
        simple = stats.segments.get("simple")
        complex_ = stats.segments.get("complex")
        if simple is None or complex_ is None or simple.trace_count == 0:
            return None
        if simple.trace_count / stats.trace_count < MIN_SEGMENT_SHARE:
            return None
        if not complex_.model_usage:
            return None

        table = get_pricing_table()
        # The model already dominant on complex (harder) traffic is treated
        # as "the current model" for this workflow.
        current_model = max(complex_.model_usage, key=lambda m: complex_.model_usage[m])
        current_rates = table.get(current_model)
        if current_rates is None or not all(k in current_rates for k in REQUIRED_PRICING_KEYS):
            return None

        current_cost_on_simple = estimate_cost(
            current_model, round(simple.avg_input_tokens), round(simple.avg_output_tokens)
        )
        if current_cost_on_simple is None or current_cost_on_simple <= 0:
            return None

        cheaper_candidates = []
        for model, rates in table.items():
            if model == current_model:
                continue
            if not all(k in rates for k in REQUIRED_PRICING_KEYS):
                continue
            candidate_cost = estimate_cost(
                model, round(simple.avg_input_tokens), round(simple.avg_output_tokens)
            )
            if candidate_cost is None:
                continue
            if candidate_cost < current_cost_on_simple:
                cheaper_candidates.append((model, candidate_cost))
        if not cheaper_candidates:
            return None

        cheapest_model, cheapest_cost = min(cheaper_candidates, key=lambda item: item[1])
        savings_pct = 1 - (float(cheapest_cost) / float(current_cost_on_simple))
        simple_share = simple.trace_count / stats.trace_count
        # Savings apply only to the simple segment's share of overall spend,
        # not the whole workflow - unlike Rule B, which switches everything.
        effective_savings_fraction = savings_pct * simple_share

        next_step = (
            f"Route the ~{simple_share:.0%} of traffic identified as low-complexity "
            f"(input under the segmentation threshold) to '{cheapest_model}' while "
            f"keeping complex traffic on '{current_model}', then compare quality "
            "and cost against the current single-model baseline."
        )
        evidence = build_evidence(
            stats,
            current_value={"model": current_model},
            ratio=simple_share,
            recommended_next_step=next_step,
            savings_fraction=effective_savings_fraction,
        )
        evidence["simple_segment_trace_count"] = simple.trace_count
        evidence["complex_segment_trace_count"] = complex_.trace_count

        return RuleDetection(
            rule_name="segmented_model_routing",
            reason=(
                f"{simple_share:.0%} of traces ({simple.trace_count} of "
                f"{stats.trace_count}) look low-complexity by input size, but currently "
                f"run on '{current_model}' alongside complex traffic. On this segment's "
                f"average token usage, '{cheapest_model}' costs an estimated {cheapest_cost} "
                f"per call vs {current_cost_on_simple} for '{current_model}'."
            ),
            current_config={"model": current_model, "segmentation": "none"},
            proposed_config={
                "simple_segment_model": cheapest_model,
                "complex_segment_model": current_model,
            },
            estimated_cost_impact=f"~{savings_pct:.0%} cost reduction on the simple segment",
            required_experiment={"description": next_step},
            evidence=evidence,
            estimated_savings_low=evidence.get("estimated_savings_low"),
            estimated_savings_high=evidence.get("estimated_savings_high"),
        )
