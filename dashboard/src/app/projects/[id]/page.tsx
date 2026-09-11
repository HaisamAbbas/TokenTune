"use client";

import Link from "next/link";
import { useParams } from "next/navigation";
import { CostLineChart } from "@/components/charts/cost-line-chart";
import { TopBar } from "@/components/top-bar";
import { Panel, StatusDot } from "@/components/ui";
import { formatCurrency, formatLatency, last30DaysRange } from "@/lib/format";
import { useOptimizations, useProject, useProjectCost, useProjectMetrics } from "@/lib/queries";

export default function OverviewPage() {
  const { id } = useParams<{ id: string }>();
  const { data: project } = useProject(id);
  const { fromTs, toTs } = last30DaysRange();

  const { data: summaryBuckets } = useProjectCost(id, fromTs, toTs);
  const { data: dayBuckets } = useProjectCost(id, fromTs, toTs, "day");
  const { data: recommendations } = useOptimizations(id);
  const { data: metrics } = useProjectMetrics(id, fromTs, toTs);

  const summary = summaryBuckets?.[0];
  const pendingCount = recommendations?.filter((r) => r.status === "pending").length ?? 0;
  const readyToAdopt =
    recommendations?.filter((r) => r.status === "pending" && r.experiment_id).length ?? 0;

  const chartData =
    dayBuckets
      ?.filter((b) => b.bucket)
      .sort((a, b) => (a.bucket! < b.bucket! ? -1 : 1))
      .map((b) => ({
        label: new Date(b.bucket!).toLocaleDateString(undefined, { month: "short", day: "numeric" }),
        cost: Number(b.total_cost ?? 0),
      })) ?? [];

  const recent = [...(recommendations ?? [])]
    .sort((a, b) => (a.created_at < b.created_at ? 1 : -1))
    .slice(0, 3);

  return (
    <>
      <TopBar title="Overview" subtitle={project?.slug} />

      <div className="flex-1 overflow-auto px-7 pb-7 flex flex-col gap-5">
        {/* KPI strip */}
        <Panel className="flex py-5.5" style={{ boxShadow: "var(--elevation-2)" }}>
          <div className="flex-1 px-7 border-r border-(--outline-variant)">
            <div className="t-label mb-2.5" style={{ color: "var(--on-surface-variant)" }}>
              TOTAL COST · 30D
            </div>
            <div className="mono" style={{ fontSize: 26, fontWeight: 500, letterSpacing: "-0.3px" }}>
              {formatCurrency(summary?.total_cost ?? 0)}
            </div>
            <div className="t-body-sm mt-1.5" style={{ color: "var(--on-surface-variant)" }}>
              {summary?.request_count ?? 0} requests
            </div>
          </div>
          <div className="flex-1 px-7 border-r border-(--outline-variant)">
            <div className="t-label mb-2.5" style={{ color: "var(--on-surface-variant)" }}>
              AVG LATENCY
            </div>
            <div className="mono" style={{ fontSize: 26, fontWeight: 500, letterSpacing: "-0.3px" }}>
              {formatLatency(summary?.avg_latency_ms ?? null)}
            </div>
            <div className="t-body-sm mt-1.5" style={{ color: "var(--on-surface-variant)" }}>
              tool-calling included
            </div>
          </div>
          <div className="flex-1 px-7 border-r border-(--outline-variant)">
            <div className="t-label mb-2.5" style={{ color: "var(--on-surface-variant)" }}>
              TOTAL TOKENS · 30D
            </div>
            <div className="mono" style={{ fontSize: 26, fontWeight: 500, letterSpacing: "-0.3px" }}>
              {(summary?.total_tokens ?? 0).toLocaleString()}
            </div>
            <div className="t-body-sm mt-1.5" style={{ color: "var(--on-surface-variant)" }}>
              input + output
            </div>
          </div>
          <div className="flex-1 px-7 border-r border-(--outline-variant)">
            <div className="t-label mb-2.5" style={{ color: "var(--on-surface-variant)" }}>
              OPEN RECOMMENDATIONS
            </div>
            <div className="mono" style={{ fontSize: 26, fontWeight: 500, letterSpacing: "-0.3px" }}>
              {pendingCount}
            </div>
            {pendingCount > 0 ? (
              <div className="mt-1.5">
                <StatusDot status="pending">{readyToAdopt} ready to adopt</StatusDot>
              </div>
            ) : (
              <div className="t-body-sm mt-1.5" style={{ color: "var(--on-surface-variant)" }}>
                none open
              </div>
            )}
          </div>
          <div className="flex-1 px-7">
            <div className="t-label mb-2.5" style={{ color: "var(--on-surface-variant)" }}>
              POTENTIAL SAVINGS · 30D
            </div>
            <div className="mono" style={{ fontSize: 26, fontWeight: 500, letterSpacing: "-0.3px" }}>
              {metrics
                ? `${formatCurrency(metrics.total_potential_savings_low, 2)}–${formatCurrency(
                    metrics.total_potential_savings_high,
                    2,
                  )}`
                : "—"}
            </div>
            <div className="t-body-sm mt-1.5" style={{ color: "var(--on-surface-variant)" }}>
              across {metrics?.open_opportunity_count ?? 0} open opportunit
              {metrics?.open_opportunity_count === 1 ? "y" : "ies"}
            </div>
          </div>
        </Panel>

        {/* Chart + recommendations */}
        <div className="grid gap-5 flex-1 min-h-0" style={{ gridTemplateColumns: "1.6fr 1fr" }}>
          <Panel className="p-6 flex flex-col">
            <div className="t-title mb-5">Cost by day</div>
            <div className="flex-1 min-h-[180px]">
              <CostLineChart data={chartData} />
            </div>
          </Panel>

          <Panel className="py-2 flex flex-col">
            <div className="t-title" style={{ padding: "14px 24px 12px" }}>
              Recent recommendations
            </div>

            {recent.length === 0 && (
              <div className="t-body-sm px-6 py-3 border-t border-(--outline-variant)" style={{ color: "var(--on-surface-variant)" }}>
                No recommendations yet — run analysis from the Optimize tab.
              </div>
            )}

            {recent.map((r) => (
              <div key={r.id} className="flex flex-col gap-1.5 px-6 py-3 border-t border-(--outline-variant)">
                <div className="flex justify-between items-center">
                  <span className="t-body" style={{ fontWeight: 500 }}>
                    {r.rule_name.replaceAll("_", " ")}
                  </span>
                  <StatusDot status={r.status}>
                    {r.status[0].toUpperCase() + r.status.slice(1)}
                  </StatusDot>
                </div>
                <span className="t-body-sm" style={{ color: "var(--on-surface-variant)" }}>
                  {r.estimated_cost_impact}
                </span>
              </div>
            ))}

            <div className="mt-auto px-6 border-t border-(--outline-variant)" style={{ padding: "14px 24px 6px" }}>
              <Link href={`/projects/${id}/optimizations`} className="t-body-sm" style={{ fontWeight: 500 }}>
                View all optimizations →
              </Link>
            </div>
          </Panel>
        </div>
      </div>
    </>
  );
}
