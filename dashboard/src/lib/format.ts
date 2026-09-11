export function formatCurrency(value: number | null | undefined, digits = 4) {
  if (value === null || value === undefined) return "$0.00";
  return `$${value.toFixed(digits)}`;
}

export function formatLatency(ms: number | null | undefined) {
  if (ms === null || ms === undefined) return "—";
  if (ms >= 1000) return `${(ms / 1000).toFixed(1)}s`;
  return `${Math.round(ms)}ms`;
}

export function formatPct(value: number | null | undefined, digits = 1) {
  if (value === null || value === undefined) return "—";
  return `${value.toFixed(digits)}%`;
}

export function last30DaysRange() {
  const to = new Date();
  const from = new Date(to.getTime() - 30 * 24 * 60 * 60 * 1000);
  return { fromTs: from.toISOString(), toTs: to.toISOString() };
}

export function metricLabel(metricName: string) {
  return metricName
    .split("_")
    .map((word) => word[0].toUpperCase() + word.slice(1))
    .join(" ");
}

export function statusLabel(status: string) {
  switch (status) {
    case "experiment_created":
      return "Experiment created";
    case "experiment_running":
      return "Experiment running";
    case "validated":
      return "Validated";
    default:
      return status[0].toUpperCase() + status.slice(1);
  }
}

export function ruleLabel(ruleName: string) {
  switch (ruleName) {
    case "excessive_retrieval_context":
      return { title: "Excessive retrieval context", code: "RULE A" };
    case "model_cost_optimization":
      return { title: "Model cost optimization", code: "RULE B" };
    case "prompt_optimization":
      return { title: "Prompt size / caching", code: "RULE C" };
    case "unnecessary_generation_calls":
      return { title: "Unnecessary generation calls", code: "RULE D" };
    case "segmented_model_routing":
      return { title: "Segmented model routing", code: "RULE E" };
    default:
      return { title: ruleName, code: "" };
  }
}
