"use client";

import { Bar, BarChart, Cell, LabelList, ResponsiveContainer, XAxis, YAxis } from "recharts";

export interface CostBarPoint {
  label: string;
  cost: number;
  highlight?: boolean;
}

function formatCost(v: number) {
  return `$${v.toFixed(5)}`;
}

export function CostBarChart({ data }: { data: CostBarPoint[] }) {
  return (
    <ResponsiveContainer width="100%" height="100%" minHeight={160}>
      <BarChart data={data} margin={{ top: 24, right: 8, left: 0, bottom: 0 }}>
        <YAxis
          axisLine={{ stroke: "var(--outline-variant)" }}
          tickLine={false}
          tick={{ fontSize: 9, fill: "var(--on-surface-variant)", fontFamily: "var(--font-roboto-mono)" }}
          tickFormatter={(v: number) => v.toFixed(3)}
          width={34}
        />
        <XAxis
          dataKey="label"
          axisLine={{ stroke: "var(--outline-variant)" }}
          tickLine={false}
          tick={{ fontSize: 12, fill: "var(--on-surface-variant)", fontFamily: "var(--font-roboto)" }}
        />
        <Bar dataKey="cost" radius={[4, 4, 0, 0]} isAnimationActive={false} maxBarSize={48}>
          {data.map((d, i) => (
            <Cell key={i} fill={d.highlight ? "var(--primary)" : "var(--surface-container-high)"} />
          ))}
          <LabelList
            dataKey="cost"
            position="top"
            formatter={(v: React.ReactNode) => (typeof v === "number" ? formatCost(v) : "")}
            style={{ fontSize: 10, fontWeight: 600, fontFamily: "var(--font-roboto-mono)", fill: "var(--on-surface)" }}
          />
        </Bar>
      </BarChart>
    </ResponsiveContainer>
  );
}
