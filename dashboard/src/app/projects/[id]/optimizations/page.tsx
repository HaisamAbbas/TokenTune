"use client";

import Link from "next/link";
import { useParams } from "next/navigation";
import { useState } from "react";
import { ArrowRightIcon, RefreshIcon } from "@/components/icons";
import { CreateExperimentDialog } from "@/components/create-experiment-dialog";
import { TopBar } from "@/components/top-bar";
import { Button, ConfigPill, Filter, Panel, StatusDot } from "@/components/ui";
import { last30DaysRange, ruleLabel } from "@/lib/format";
import {
  useAnalyzeOptimizations,
  useOptimizations,
  useProject,
  useUpdateOptimizationStatus,
} from "@/lib/queries";
import type { OptimizationRecommendation, RecommendationStatus } from "@/lib/types";

type FilterValue = "all" | RecommendationStatus;

export default function OptimizationsPage() {
  const { id } = useParams<{ id: string }>();
  const { data: project } = useProject(id);
  const { data: recommendations, isLoading } = useOptimizations(id);
  const analyze = useAnalyzeOptimizations(id);
  const updateStatus = useUpdateOptimizationStatus(id);

  const [filter, setFilter] = useState<FilterValue>("all");
  const [experimentTarget, setExperimentTarget] = useState<OptimizationRecommendation | null>(null);

  const all = recommendations ?? [];
  const counts = {
    all: all.length,
    pending: all.filter((r) => r.status === "pending").length,
    adopted: all.filter((r) => r.status === "adopted").length,
    rejected: all.filter((r) => r.status === "rejected").length,
  };
  const filtered = filter === "all" ? all : all.filter((r) => r.status === filter);

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
          <Filter active={filter === "pending"} onClick={() => setFilter("pending")}>
            Pending · {counts.pending}
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
            return (
              <div key={r.id} className="row">
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

                <div style={{ width: 130, flexShrink: 0 }}>
                  <div className="t-body" style={{ fontWeight: 500 }}>
                    {r.estimated_cost_impact}
                  </div>
                  <div className="t-body-sm" style={{ color: "var(--on-surface-variant)" }}>
                    {r.confidence.toFixed(2)} confidence
                  </div>
                </div>

                <div style={{ width: 100, flexShrink: 0 }}>
                  <StatusDot status={r.status}>{r.status[0].toUpperCase() + r.status.slice(1)}</StatusDot>
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
