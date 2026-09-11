"use client";

import Link from "next/link";
import { useParams } from "next/navigation";
import { CostLineChart } from "@/components/charts/cost-line-chart";
import { ClockIcon, CostIcon, OptimizeIcon, TokensIcon } from "@/components/icons";
import { TopBar } from "@/components/top-bar";
import { Panel, StatCard, StatusDot } from "@/components/ui";
import { formatCurrency, formatLatency, last30DaysRange } from "@/lib/format";
import { useOptimizations, useProject, useProjectCost } from "@/lib/queries";

export default function OverviewPage() {
  const { id } = useParams<{ id: string }>();
  const { data: project } = useProject(id);
  const { fromTs, toTs } = last30DaysRange();

  const { data: summaryBuckets } = useProjectCost(id, fromTs, toTs);
  const { data: dayBuckets } = useProjectCost(id, fromTs, toTs, "day");
  const { data: recommendations } = useOptimizations(id);

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
        {/* KPI strip - each stat has its own color identity (accent bar +
            tinted icon badge) rather than being an interchangeable box in a
            row of identical cards. */}
        <div className="grid gap-4" style={{ gridTemplateColumns: "repeat(4, minmax(0, 1fr))" }}>
          <StatCard
            icon={<CostIcon size={18} />}
            accent="var(--primary)"
            label="TOTAL COST · 30D"
            value={formatCurrency(summary?.total_cost ?? 0)}
            caption={`${summary?.request_count ?? 0} requests`}
          />
          <StatCard
            icon={<ClockIcon size={18} />}
            accent="var(--secondary)"
            label="AVG LATENCY"
            value={formatLatency(summary?.avg_latency_ms ?? null)}
            caption="tool-calling included"
          />
          <StatCard
            icon={<TokensIcon size={18} />}
            accent="var(--warning)"
            label="TOTAL TOKENS · 30D"
            value={(summary?.total_tokens ?? 0).toLocaleString()}
            caption="input + output"
          />
          <StatCard
            icon={<OptimizeIcon size={18} />}
            accent="var(--success)"
            label="OPEN RECOMMENDATIONS"
            value={pendingCount}
            caption={
              pendingCount > 0 ? (
                <StatusDot status="pending">{readyToAdopt} ready to adopt</StatusDot>
              ) : (
                "none open"
              )
            }
          />
        </div>

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
