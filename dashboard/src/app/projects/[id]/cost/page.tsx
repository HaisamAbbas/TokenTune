"use client";

import { useParams } from "next/navigation";
import { useState } from "react";
import { CostLineChart } from "@/components/charts/cost-line-chart";
import { TopBar } from "@/components/top-bar";
import { Filter, Panel } from "@/components/ui";
import { formatCurrency, formatLatency, last30DaysRange } from "@/lib/format";
import { useProject, useProjectCost } from "@/lib/queries";
import type { GroupBy } from "@/lib/types";

export default function CostPage() {
  const { id } = useParams<{ id: string }>();
  const { data: project } = useProject(id);
  const { fromTs, toTs } = last30DaysRange();
  const [breakdown, setBreakdown] = useState<Extract<GroupBy, "model" | "workflow">>("model");

  const { data: dayBuckets } = useProjectCost(id, fromTs, toTs, "day");
  const { data: breakdownBuckets, isLoading } = useProjectCost(id, fromTs, toTs, breakdown);

  const chartData =
    dayBuckets
      ?.filter((b) => b.bucket)
      .sort((a, b) => (a.bucket! < b.bucket! ? -1 : 1))
      .map((b) => ({
        label: new Date(b.bucket!).toLocaleDateString(undefined, { month: "short", day: "numeric" }),
        cost: Number(b.total_cost ?? 0),
      })) ?? [];

  const rows = [...(breakdownBuckets ?? [])].sort(
    (a, b) => Number(b.total_cost ?? 0) - Number(a.total_cost ?? 0),
  );

  return (
    <>
      <TopBar title="Cost" subtitle={project?.slug} />

      <div className="flex-1 overflow-auto px-7 pb-7 flex flex-col gap-5">
        <Panel className="p-6 flex flex-col" style={{ height: 260 }}>
          <div className="t-title mb-5">Cost by day · last 30 days</div>
          <div className="flex-1 min-h-[140px]">
            <CostLineChart data={chartData} />
          </div>
        </Panel>

        <div className="flex gap-2">
          <Filter active={breakdown === "model"} onClick={() => setBreakdown("model")}>
            By model
          </Filter>
          <Filter active={breakdown === "workflow"} onClick={() => setBreakdown("workflow")}>
            By workflow
          </Filter>
        </div>

        <Panel className="overflow-hidden">
          <div className="row" style={{ borderTop: "none" }}>
            <div className="t-label" style={{ color: "var(--on-surface-variant)", flex: 1 }}>
              {breakdown === "model" ? "MODEL" : "WORKFLOW"}
            </div>
            <div className="t-label mono" style={{ color: "var(--on-surface-variant)", width: 130 }}>
              TOTAL COST
            </div>
            <div className="t-label mono" style={{ color: "var(--on-surface-variant)", width: 130 }}>
              TOTAL TOKENS
            </div>
            <div className="t-label mono" style={{ color: "var(--on-surface-variant)", width: 110 }}>
              AVG LATENCY
            </div>
            <div className="t-label mono" style={{ color: "var(--on-surface-variant)", width: 100 }}>
              REQUESTS
            </div>
          </div>

          {isLoading && (
            <div className="row t-body-sm" style={{ color: "var(--on-surface-variant)" }}>
              Loading…
            </div>
          )}
          {!isLoading && rows.length === 0 && (
            <div className="row t-body-sm" style={{ color: "var(--on-surface-variant)" }}>
              No cost data in this range yet.
            </div>
          )}
          {rows.map((r, i) => (
            <div key={i} className="row">
              <div className="t-body" style={{ fontWeight: 500, flex: 1 }}>
                {r.bucket ?? "unknown"}
              </div>
              <div className="t-body mono" style={{ width: 130 }}>
                {formatCurrency(r.total_cost)}
              </div>
              <div className="t-body mono" style={{ width: 130 }}>
                {r.total_tokens.toLocaleString()}
              </div>
              <div className="t-body mono" style={{ width: 110 }}>
                {formatLatency(r.avg_latency_ms)}
              </div>
              <div className="t-body mono" style={{ width: 100 }}>
                {r.request_count}
              </div>
            </div>
          ))}
        </Panel>
      </div>
    </>
  );
}
