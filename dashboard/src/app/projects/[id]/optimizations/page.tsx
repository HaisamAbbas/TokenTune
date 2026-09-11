"use client";

import Link from "next/link";
import { useParams } from "next/navigation";
import { Fragment, useState } from "react";
import { ArrowRightIcon, RefreshIcon } from "@/components/icons";
import { CreateExperimentDialog } from "@/components/create-experiment-dialog";
import { TopBar } from "@/components/top-bar";
import { Button, ConfidenceBadge, ConfigPill, Filter, Panel, StatusDot } from "@/components/ui";
import { formatCurrency, last30DaysRange, ruleLabel, statusLabel } from "@/lib/format";
import {
  useAnalyzeOptimizations,
  useOptimizations,
  useProject,
  useUpdateOptimizationStatus,
} from "@/lib/queries";
import type {
  OptimizationRecommendation,
  RecommendationEvidence,
  RecommendationStatus,
} from "@/lib/types";

type FilterValue = "all" | "open" | "adopted" | "rejected";

const OPEN_STATUSES: RecommendationStatus[] = [
  "pending",
  "experiment_created",
  "experiment_running",
  "validated",
];

export default function OptimizationsPage() {
  const { id } = useParams<{ id: string }>();
  const { data: project } = useProject(id);
  const { data: recommendations, isLoading } = useOptimizations(id);
  const analyze = useAnalyzeOptimizations(id);
  const updateStatus = useUpdateOptimizationStatus(id);

  const [filter, setFilter] = useState<FilterValue>("all");
  const [experimentTarget, setExperimentTarget] = useState<OptimizationRecommendation | null>(null);
  const [expandedId, setExpandedId] = useState<string | null>(null);

  const all = recommendations ?? [];
  const counts = {
    all: all.length,
    open: all.filter((r) => OPEN_STATUSES.includes(r.status)).length,
    adopted: all.filter((r) => r.status === "adopted").length,
    rejected: all.filter((r) => r.status === "rejected").length,
  };
  const filtered =
    filter === "all"
      ? all
      : filter === "open"
        ? all.filter((r) => OPEN_STATUSES.includes(r.status))
        : all.filter((r) => r.status === filter);

  async function handleAnalyze() {
    const { fromTs, toTs } = last30DaysRange();
    await analyze.mutateAsync({ fromTs, toTs });
  }

  return (
    <>
      <TopBar
        title="Optimizations"
        subtitle={project?.slug}
        action={
          <Button variant="outline" onClick={handleAnalyze} disabled={analyze.isPending}>
            <RefreshIcon />
            {analyze.isPending ? "Analyzing…" : "Run analysis"}
          </Button>
        }
      />

      <div className="flex-1 overflow-auto px-7 pb-7 flex flex-col gap-4">
        {analyze.isError && (
          <div className="t-body-sm" style={{ color: "var(--error)" }}>
            {(analyze.error as Error).message}
          </div>
        )}
        {analyze.isSuccess && (
          <div className="t-body-sm" style={{ color: "var(--success)" }}>
            {analyze.data.recommendations_created} new recommendation(s) created.
          </div>
        )}

        <div className="flex gap-2">
          <Filter active={filter === "all"} onClick={() => setFilter("all")}>
            All · {counts.all}
          </Filter>
          <Filter active={filter === "open"} onClick={() => setFilter("open")}>
            Open · {counts.open}
          </Filter>
          <Filter active={filter === "adopted"} onClick={() => setFilter("adopted")}>
            Adopted · {counts.adopted}
          </Filter>
          <Filter active={filter === "rejected"} onClick={() => setFilter("rejected")}>
            Rejected · {counts.rejected}
          </Filter>
        </div>

        <Panel className="overflow-hidden">
          {isLoading && (
            <div className="row t-body-sm" style={{ color: "var(--on-surface-variant)", borderTop: "none" }}>
              Loading…
            </div>
          )}
          {!isLoading && filtered.length === 0 && (
            <div className="row t-body-sm" style={{ color: "var(--on-surface-variant)", borderTop: "none" }}>
              No recommendations{filter !== "all" ? ` with status "${filter}"` : ""} yet.
            </div>
          )}
          {filtered.map((r) => {
            const { title, code } = ruleLabel(r.rule_name);
            const currentPill = firstConfigEntry(r.current_config);
            const proposedPill = firstConfigEntry(r.proposed_config);
            const hasSavingsEstimate =
              r.estimated_savings_low !== null && r.estimated_savings_high !== null;
            const isExpanded = expandedId === r.id;
            return (
              <Fragment key={r.id}>
                <div className="row">
                  <div style={{ flex: 1, minWidth: 0 }}>
                    <div className="flex items-center gap-2.5 mb-1">
                      <span className="t-body" style={{ fontWeight: 500 }}>
                        {title}
                      </span>
                      <span className="t-label" style={{ color: "var(--on-surface-variant)", fontWeight: 400 }}>
                        {code}
                      </span>
                    </div>
                    <div className="t-body-sm mb-2.5" style={{ color: "var(--on-surface-variant)" }}>
                      {r.workflow ?? "—"}
                    </div>
                    <div
                      className="t-body-sm"
                      style={{ color: "var(--on-surface-variant)", maxWidth: 520, lineHeight: 1.5 }}
                    >
                      {r.reason}
                    </div>
                    {r.evidence && (
                      <button
                        className="t-body-sm"
                        style={{
                          color: "var(--primary)",
                          fontWeight: 500,
                          marginTop: 8,
                          background: "none",
                          border: "none",
                          cursor: "pointer",
                          padding: 0,
                        }}
                        onClick={() => setExpandedId(isExpanded ? null : r.id)}
                      >
                        {isExpanded ? "Hide evidence ▲" : "Show evidence ▼"}
                      </button>
                    )}
                  </div>

                  <div style={{ width: 220, flexShrink: 0 }} className="flex items-center gap-2">
                    {currentPill && <ConfigPill>{currentPill}</ConfigPill>}
                    {currentPill && proposedPill && (
                      <span style={{ color: "var(--on-surface-variant)", flexShrink: 0 }}>
                        <ArrowRightIcon />
                      </span>
                    )}
                    {proposedPill && <ConfigPill highlight>{proposedPill}</ConfigPill>}
                  </div>

                  <div style={{ width: 160, flexShrink: 0 }}>
                    <div className="t-body" style={{ fontWeight: 500 }}>
                      {hasSavingsEstimate
                        ? `${formatCurrency(r.estimated_savings_low, 2)}–${formatCurrency(
                            r.estimated_savings_high,
                            2,
                          )}/mo`
                        : r.estimated_cost_impact}
                    </div>
                    <div style={{ marginTop: 4 }}>
                      <ConfidenceBadge bucket={r.confidence_bucket} />
                    </div>
                  </div>

                  <div style={{ width: 130, flexShrink: 0 }}>
                    <StatusDot status={r.status}>{statusLabel(r.status)}</StatusDot>
                  </div>

                  <div style={{ width: 170, flexShrink: 0 }} className="flex gap-2 justify-end">
                    {r.status === "pending" && !r.experiment_id && (
                      <>
                        <Button
                          variant="text"
                          className="t-body-sm"
                          style={{ fontWeight: 500 }}
                          onClick={() => updateStatus.mutate({ recommendationId: r.id, status: "rejected" })}
                          disabled={updateStatus.isPending}
                        >
                          Reject
                        </Button>
                        <Button
                          style={{ height: 32, padding: "0 14px" }}
                          onClick={() => setExperimentTarget(r)}
                        >
                          Experiment
                        </Button>
                      </>
                    )}
                    {r.experiment_id && (
                      <Link
                        href={`/projects/${id}/experiments/${r.experiment_id}`}
                        className="t-body-sm"
                        style={{ fontWeight: 500 }}
                      >
                        View experiment →
                      </Link>
                    )}
                    {r.status === "rejected" && !r.experiment_id && (
                      <span className="t-body-sm" style={{ color: "var(--on-surface-variant)" }}>
                        rejected
                      </span>
                    )}
                  </div>
                </div>
                {isExpanded && r.evidence && <EvidencePanel evidence={r.evidence} />}
              </Fragment>
            );
          })}
        </Panel>
      </div>

      <CreateExperimentDialog
        projectId={id}
        recommendation={experimentTarget}
        open={experimentTarget !== null}
        onOpenChange={(open) => !open && setExperimentTarget(null)}
      />
    </>
  );
}

function firstConfigEntry(config: Record<string, unknown>): string | null {
  const entries = Object.entries(config ?? {});
  if (entries.length === 0) return null;
  const [k, v] = entries[0];
  return `${k}: ${v}`;
}

function EvidencePanel({ evidence }: { evidence: RecommendationEvidence }) {
  const fields: Array<[string, string]> = [
    ["Sample size", `${evidence.sample_size} traces`],
    ["Avg input tokens", evidence.avg_input_tokens.toLocaleString()],
  ];
  if (evidence.p95_input_tokens !== null) {
    fields.push(["P95 input tokens", evidence.p95_input_tokens.toLocaleString()]);
  }
  if (evidence.ratio !== null) {
    fields.push(["Ratio", `${(evidence.ratio * 100).toFixed(0)}%`]);
  }
  fields.push(["Estimated monthly cost", formatCurrency(evidence.estimated_monthly_cost, 2)]);
  fields.push([
    "Quality evidence",
    evidence.quality_evidence === "validated" ? "Validated by experiment" : "Not yet tested",
  ]);

  return (
    <div
      className="t-body-sm"
      style={{
        padding: "16px 24px",
        background: "var(--surface-container)",
        borderTop: "1px solid var(--outline-variant)",
      }}
    >
      <div
        className="t-label mb-3"
        style={{ color: "var(--on-surface-variant)", letterSpacing: 0.4 }}
      >
        WHY WE THINK THIS
      </div>
      <div
        className="grid gap-x-8 gap-y-2 mb-3"
        style={{ gridTemplateColumns: "repeat(auto-fit, minmax(180px, 1fr))" }}
      >
        {fields.map(([label, value]) => (
          <div key={label}>
            <div style={{ color: "var(--on-surface-variant)" }}>{label}</div>
            <div className="mono" style={{ fontWeight: 500 }}>
              {value}
            </div>
          </div>
        ))}
      </div>
      <div style={{ color: "var(--on-surface-variant)" }}>
        <span style={{ fontWeight: 500, color: "var(--on-surface)" }}>Recommended next step: </span>
        {evidence.recommended_next_step}
      </div>
    </div>
  );
}
