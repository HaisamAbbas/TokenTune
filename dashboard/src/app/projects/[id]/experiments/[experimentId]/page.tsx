"use client";

import { useParams } from "next/navigation";
import { useMemo } from "react";
import { CostBarChart } from "@/components/charts/cost-bar-chart";
import { ArrowRightIcon, ArrowUpIcon } from "@/components/icons";
import { Button, ConfigPill, Panel } from "@/components/ui";
import { computeComparison } from "@/lib/compare";
import { formatCurrency, formatLatency, formatPct, metricLabel } from "@/lib/format";
import {
  useExperiment,
  useExperimentRuns,
  useProject,
  useRunExperiment,
  useUpdateOptimizationStatus,
} from "@/lib/queries";

export default function ExperimentDetailPage() {
  const { id, experimentId } = useParams<{ id: string; experimentId: string }>();
  const { data: project } = useProject(id);
  const { data: experiment, isLoading } = useExperiment(id, experimentId);
  const { data: runs } = useExperimentRuns(id, experimentId);
  const runExperiment = useRunExperiment(id, experimentId);
  const updateStatus = useUpdateOptimizationStatus(id);

  // `runs` is ordered oldest-first (an experiment can be retried after a
  // failure, accumulating rows rather than replacing them) - the most
  // recent attempt per variant is the last match, not the first.
  const baselineRun = runs?.filter((r) => r.variant === "baseline").at(-1);
  const experimentRun = runs?.filter((r) => r.variant === "experiment").at(-1);

  const comparison = useMemo(() => {
    if (!baselineRun || !experimentRun) return null;
    return computeComparison(baselineRun, experimentRun);
  }, [baselineRun, experimentRun]);

  if (isLoading || !experiment) {
    return (
      <>
        <ExperimentTopBar name="" projectSlug={project?.slug} />
        <div className="flex-1 flex items-center justify-center t-body-sm" style={{ color: "var(--on-surface-variant)" }}>
          Loading…
        </div>
      </>
    );
  }

  const canAdopt = experiment.status === "completed" && Boolean(experiment.recommendation_id);
  const adoptDisabledReason = !experiment.recommendation_id
    ? "This experiment isn't linked to a recommendation, so there's nothing to adopt."
    : experiment.status !== "completed"
      ? "Only a completed experiment can be adopted."
      : null;

  return (
    <>
      <ExperimentTopBar name={experiment.name} projectSlug={project?.slug} />

      <div className="flex-1 overflow-auto px-7 pb-7 flex flex-col gap-5">
        <div className="flex justify-between items-center flex-wrap gap-3">
          <div className="flex items-center gap-3.5">
            <span
              className="t-body-sm"
              style={{
                background: "var(--surface-container-high)",
                padding: "6px 12px",
                borderRadius: 999,
                display: "inline-flex",
                alignItems: "center",
                gap: 6,
              }}
            >
              <span
                className="dot"
                style={{
                  width: 7,
                  height: 7,
                  borderRadius: "50%",
                  background:
                    experiment.status === "completed"
                      ? "var(--success)"
                      : experiment.status === "failed"
                        ? "var(--error)"
                        : "var(--on-surface-variant)",
                }}
              />
              {experiment.status[0].toUpperCase() + experiment.status.slice(1)}
            </span>
            {experimentRun && (
              <span className="t-body-sm" style={{ color: "var(--on-surface-variant)" }}>
                {experimentRun.metrics.request_count} evaluation items
                {experimentRun.completed_at &&
                  ` · finished ${new Date(experimentRun.completed_at).toLocaleString()}`}
              </span>
            )}
          </div>

          {experiment.status === "completed" && (
            <div className="flex gap-2.5">
              <Button
                variant="outline-error"
                disabled={!experiment.recommendation_id || updateStatus.isPending}
                onClick={() =>
                  experiment.recommendation_id &&
                  updateStatus.mutate({ recommendationId: experiment.recommendation_id, status: "rejected" })
                }
              >
                Reject
              </Button>
              <div className="flex flex-col items-end gap-1">
                <Button
                  disabled={!canAdopt || updateStatus.isPending}
                  onClick={() =>
                    experiment.recommendation_id &&
                    updateStatus.mutate({ recommendationId: experiment.recommendation_id, status: "adopted" })
                  }
                >
                  Adopt
                </Button>
                {adoptDisabledReason && (
                  <span className="t-body-sm" style={{ color: "var(--on-surface-variant)" }}>
                    {adoptDisabledReason}
                  </span>
                )}
              </div>
            </div>
          )}
        </div>

        {updateStatus.isError && (
          <div className="t-body-sm" style={{ color: "var(--error)" }}>
            {(updateStatus.error as Error).message}
          </div>
        )}
        {updateStatus.isSuccess && (
          <div className="t-body-sm" style={{ color: "var(--success)" }}>
            Recommendation {updateStatus.data.status}.
          </div>
        )}

        <div className="flex items-center gap-2.5 flex-wrap">
          <span className="t-label" style={{ color: "var(--on-surface-variant)" }}>
            BASELINE
          </span>
          <ConfigPill>{JSON.stringify(experiment.baseline_config)}</ConfigPill>
          <span style={{ color: "var(--on-surface-variant)" }}>
            <ArrowRightIcon />
          </span>
          <span className="t-label" style={{ color: "var(--on-surface-variant)" }}>
            EXPERIMENT
          </span>
          <ConfigPill highlight>{JSON.stringify(experiment.experiment_config)}</ConfigPill>
        </div>

        {(experiment.status === "pending" || experiment.status === "running") && (
          <Panel className="p-7 flex flex-col items-center gap-3 text-center">
            <Spinner />
            <div className="t-title">
              {runExperiment.isPending || experiment.status === "running"
                ? "Running experiment…"
                : "This experiment hasn't been run yet"}
            </div>
            <div className="t-body-sm" style={{ color: "var(--on-surface-variant)", maxWidth: 480 }}>
              Running executes both configs against the real sample app for every item in the
              evaluation dataset, then scores each answer. This is genuinely synchronous and can
              take several minutes for larger datasets — please don&apos;t navigate away while it runs.
            </div>
            {runExperiment.isError && (
              <div className="t-body-sm" style={{ color: "var(--error)" }}>
                {(runExperiment.error as Error).message}
              </div>
            )}
            {!runExperiment.isPending && (
              <Button onClick={() => runExperiment.mutate()}>Run experiment</Button>
            )}
          </Panel>
        )}

        {experiment.status === "failed" && (
          <Panel className="p-7">
            <div className="t-title mb-2" style={{ color: "var(--error)" }}>
              Experiment failed
            </div>
            <div className="t-body-sm" style={{ color: "var(--on-surface-variant)" }}>
              {experiment.error}
            </div>
            <div className="mt-4">
              <Button onClick={() => runExperiment.mutate()} disabled={runExperiment.isPending}>
                {runExperiment.isPending ? "Retrying…" : "Retry run"}
              </Button>
            </div>
          </Panel>
        )}

        {experiment.status === "completed" && baselineRun && experimentRun && comparison && (
          <>
            <Panel style={{ padding: "8px 28px 4px" }}>
              <table>
                <thead>
                  <tr>
                    <th className="t-label" style={{ color: "var(--on-surface-variant)", width: "34%" }}>
                      METRIC
                    </th>
                    <th className="t-label mono" style={{ color: "var(--on-surface-variant)", width: "22%" }}>
                      BASELINE
                    </th>
                    <th className="t-label mono" style={{ color: "var(--on-surface-variant)", width: "22%" }}>
                      EXPERIMENT
                    </th>
                    <th className="t-label" style={{ color: "var(--on-surface-variant)", width: "22%" }}>
                      CHANGE
                    </th>
                  </tr>
                </thead>
                <tbody>
                  <MetricRow
                    label="Cost / request"
                    baseline={formatCurrency(baselineRun.metrics.cost_per_request, 6)}
                    experiment={formatCurrency(experimentRun.metrics.cost_per_request, 6)}
                    deltaPct={pctFrom(baselineRun.metrics.cost_per_request, experimentRun.metrics.cost_per_request)}
                    goodDirection="down"
                  />
                  <MetricRow
                    label="Total cost"
                    baseline={formatCurrency(baselineRun.metrics.total_cost, 6)}
                    experiment={formatCurrency(experimentRun.metrics.total_cost, 6)}
                    deltaPct={comparison.cost_reduction_pct}
                    goodDirection="down"
                    invertedDelta
                  />
                  <MetricRow
                    label="Avg input tokens"
                    baseline={Math.round(baselineRun.metrics.avg_input_tokens).toLocaleString()}
                    experiment={Math.round(experimentRun.metrics.avg_input_tokens).toLocaleString()}
                    deltaPct={pctFrom(baselineRun.metrics.avg_input_tokens, experimentRun.metrics.avg_input_tokens)}
                    goodDirection="down"
                  />
                  <MetricRow
                    label="Avg output tokens"
                    baseline={Math.round(baselineRun.metrics.avg_output_tokens).toLocaleString()}
                    experiment={Math.round(experimentRun.metrics.avg_output_tokens).toLocaleString()}
                    deltaPct={pctFrom(baselineRun.metrics.avg_output_tokens, experimentRun.metrics.avg_output_tokens)}
                    goodDirection="down"
                  />
                  <MetricRow
                    label="Avg latency"
                    baseline={formatLatency(baselineRun.metrics.avg_latency_ms)}
                    experiment={formatLatency(experimentRun.metrics.avg_latency_ms)}
                    deltaPct={pctFrom(baselineRun.metrics.avg_latency_ms, experimentRun.metrics.avg_latency_ms)}
                    goodDirection="down"
                  />
                  {Object.keys(baselineRun.metrics.quality_scores).map((metricName) => {
                    const diff = comparison.quality_differences[metricName] ?? 0;
                    return (
                      <tr key={metricName}>
                        <td className="t-body">Quality ({metricLabel(metricName)})</td>
                        <td className="mono t-body">
                          {baselineRun.metrics.quality_scores[metricName].toFixed(2)}
                        </td>
                        <td className="mono t-body">
                          {experimentRun.metrics.quality_scores[metricName]?.toFixed(2) ?? "—"}
                        </td>
                        <td>
                          <span
                            className="delta"
                            style={{
                              color:
                                diff > 0
                                  ? "var(--success)"
                                  : diff < 0
                                    ? "var(--error)"
                                    : "var(--on-surface-variant)",
                            }}
                          >
                            {diff >= 0 ? "+" : ""}
                            {diff.toFixed(2)}
                          </span>
                        </td>
                      </tr>
                    );
                  })}
                </tbody>
              </table>
            </Panel>

            <div className="grid gap-5 flex-1 min-h-0" style={{ gridTemplateColumns: "1fr 1.5fr" }}>
              <Panel className="p-6 flex flex-col">
                <div className="t-title mb-5">Cost per request</div>
                <div className="flex-1 min-h-[140px]">
                  <CostBarChart
                    data={[
                      { label: "Baseline", cost: baselineRun.metrics.cost_per_request },
                      { label: "Experiment", cost: experimentRun.metrics.cost_per_request, highlight: true },
                    ]}
                  />
                </div>
              </Panel>

              <Panel
                className="p-6 flex flex-col justify-center gap-2.5"
                style={{ boxShadow: "var(--elevation-2)" }}
              >
                <div className="t-title">Summary</div>
                <div className="t-body" style={{ color: "var(--on-surface-variant)", lineHeight: 1.6 }}>
                  Switching baseline config to the experiment config changed cost per request by{" "}
                  <span style={{ color: "var(--on-surface)", fontWeight: 500 }}>
                    {formatPct(comparison.cost_reduction_pct)}
                  </span>{" "}
                  and latency by{" "}
                  <span style={{ color: "var(--on-surface)", fontWeight: 500 }}>
                    {formatPct(
                      pctFrom(baselineRun.metrics.avg_latency_ms, experimentRun.metrics.avg_latency_ms),
                    )}
                  </span>
                  , with a quality difference of{" "}
                  {Object.entries(comparison.quality_differences).map(([name, diff], i) => (
                    <span key={name}>
                      {i > 0 && ", "}
                      <span style={{ color: "var(--on-surface)", fontWeight: 500 }}>
                        {diff >= 0 ? "+" : ""}
                        {diff.toFixed(2)} {metricLabel(name)}
                      </span>
                    </span>
                  ))}
                  .
                </div>
                <div className="t-body-sm mt-1.5" style={{ color: "var(--on-surface-variant)" }}>
                  Evaluated on {experimentRun.metrics.request_count} item(s)
                  {experimentRun.metrics.request_count < 10 &&
                    " — widen the evaluation set before treating this as conclusive."}
                </div>
              </Panel>
            </div>
          </>
        )}
      </div>
    </>
  );
}

function ExperimentTopBar({ name, projectSlug }: { name: string; projectSlug?: string }) {
  return (
    <div className="h-16 shrink-0 flex items-center px-7">
      <div className="flex items-baseline gap-2.5 min-w-0">
        <span className="t-body-sm" style={{ color: "var(--on-surface-variant)" }}>
          {projectSlug ?? "Experiments"}
        </span>
        <span className="t-body-sm" style={{ color: "var(--on-surface-variant)" }}>
          /
        </span>
        <span className="t-headline truncate" style={{ fontSize: 17 }}>
          {name}
        </span>
      </div>
    </div>
  );
}

function pctFrom(baseline: number, experiment: number) {
  if (!baseline) return 0;
  return ((baseline - experiment) / baseline) * 100;
}

function MetricRow({
  label,
  baseline,
  experiment,
  deltaPct,
}: {
  label: string;
  baseline: string;
  experiment: string;
  deltaPct: number;
  goodDirection: "down" | "up";
  invertedDelta?: boolean;
}) {
  const improved = deltaPct > 0;
  return (
    <tr>
      <td className="t-body">{label}</td>
      <td className="mono t-body">{baseline}</td>
      <td className="mono t-body">{experiment}</td>
      <td>
        <span
          className="delta"
          style={{ color: improved ? "var(--success)" : deltaPct < 0 ? "var(--error)" : "var(--on-surface-variant)" }}
        >
          {improved && <ArrowUpIcon />}
          {formatPct(Math.abs(deltaPct))}
        </span>
      </td>
    </tr>
  );
}

function Spinner() {
  return (
    <svg
      width="28"
      height="28"
      viewBox="0 0 24 24"
      fill="none"
      stroke="var(--primary)"
      strokeWidth="2.5"
      style={{ animation: "spin 0.9s linear infinite" }}
    >
      <style>{"@keyframes spin { to { transform: rotate(360deg); } }"}</style>
      <path d="M21 12a9 9 0 1 1-2.6-6.4" strokeLinecap="round" />
    </svg>
  );
}
