"use client";

import {
  Area,
  AreaChart,
  CartesianGrid,
  ResponsiveContainer,
  Tooltip,
  XAxis,
} from "recharts";

export interface CostLinePoint {
  label: string;
  cost: number;
}

function CostTooltip({
  active,
  payload,
  label,
}: {
  active?: boolean;
  payload?: { value: number }[];
  label?: string;
}) {
  if (!active || !payload?.length) return null;
  return (
    <div
      className="t-body-sm mono"
      style={{
        background: "var(--surface-container-high)",
        borderRadius: 8,
        padding: "6px 10px",
        boxShadow: "var(--elevation-1)",
      }}
    >
      <div style={{ color: "var(--on-surface-variant)" }}>{label}</div>
      <div style={{ fontWeight: 500 }}>${payload[0].value.toFixed(4)}</div>
    </div>
  );
}

function EndDot(props: { cx?: number; cy?: number; index?: number; dataLength: number }) {
  const { cx, cy, index, dataLength } = props;
  if (index !== dataLength - 1 || cx === undefined || cy === undefined) return null;
  return <circle cx={cx} cy={cy} r={4} fill="var(--primary)" />;
}

export function CostLineChart({ data }: { data: CostLinePoint[] }) {
  if (data.length === 0) {
    return (
      <div className="flex-1 flex items-center justify-center t-body-sm" style={{ color: "var(--on-surface-variant)" }}>
        No cost data in this range yet.
      </div>
    );
  }

  return (
    <ResponsiveContainer width="100%" height="100%" minHeight={180}>
      <AreaChart data={data} margin={{ top: 20, right: 4, left: 4, bottom: 0 }}>
        <defs>
          <linearGradient id="costFill" x1="0" y1="0" x2="0" y2="1">
            <stop offset="0%" stopColor="var(--primary)" stopOpacity={0.16} />
            <stop offset="100%" stopColor="var(--primary)" stopOpacity={0} />
          </linearGradient>
        </defs>
        <CartesianGrid vertical={false} stroke="var(--outline-variant)" />
        <XAxis
          dataKey="label"
          axisLine={false}
          tickLine={false}
          interval="preserveStartEnd"
          tick={{ fontSize: 11, fill: "var(--on-surface-variant)", fontFamily: "var(--font-roboto)" }}
          dy={8}
        />
        <Tooltip content={<CostTooltip />} />
        <Area
          type="monotone"
          dataKey="cost"
          stroke="var(--primary)"
          strokeWidth={2.5}
          fill="url(#costFill)"
          dot={(props) => (
            <EndDot key={props.index} {...props} dataLength={data.length} />
          )}
          activeDot={{ r: 4, fill: "var(--primary)" }}
          isAnimationActive={false}
        />
      </AreaChart>
    </ResponsiveContainer>
  );
}
