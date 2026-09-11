import type { ExperimentRun } from "./types";

// Mirrors backend/app/services/experiments.py::compare_runs — used to derive
// the comparison numbers for an experiment that already completed in a
// previous request (GET .../runs only returns raw per-variant metrics; the
// derived percentages are only returned inline by POST .../run).
export function computeComparison(baselineRun: ExperimentRun, experimentRun: ExperimentRun) {
  const baseline = baselineRun.metrics;
  const experiment = experimentRun.metrics;

  const baselineCost = baseline.total_cost;
  const experimentCost = experiment.total_cost;
  const costReductionPct =
    baselineCost > 0 ? ((baselineCost - experimentCost) / baselineCost) * 100 : 0;

  const baselineTokens = baseline.avg_input_tokens + baseline.avg_output_tokens;
  const experimentTokens = experiment.avg_input_tokens + experiment.avg_output_tokens;
  const tokenReductionPct =
    baselineTokens > 0 ? ((baselineTokens - experimentTokens) / baselineTokens) * 100 : 0;

  const qualityDifference = experiment.quality_score - baseline.quality_score;
  const latencyDifferenceMs = experiment.avg_latency_ms - baseline.avg_latency_ms;

  return {
    cost_reduction_pct: costReductionPct,
    quality_difference: qualityDifference,
    latency_difference_ms: latencyDifferenceMs,
    token_reduction_pct: tokenReductionPct,
  };
}
