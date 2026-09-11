import { cn } from "@/lib/cn";
import type { ButtonHTMLAttributes } from "react";

export function Panel({
  className,
  style,
  children,
}: {
  className?: string;
  style?: React.CSSProperties;
  children: React.ReactNode;
}) {
  return (
    <div className={cn("panel", className)} style={style}>
      {children}
    </div>
  );
}

/** A single KPI stat card with a distinct color identity (accent top bar +
 * tinted icon badge) - deliberately NOT an interchangeable box in a grid of
 * identical white cards (that reads as generic AI-dashboard filler). Each
 * card's `accent` should be a different token so the row reads as several
 * distinct things at a glance, not one repeated shape. */
export function StatCard({
  icon,
  accent,
  label,
  value,
  caption,
  className,
}: {
  icon: React.ReactNode;
  accent: string;
  label: string;
  value: React.ReactNode;
  caption?: React.ReactNode;
  className?: string;
}) {
  return (
    <div
      className={cn("panel stat-card", className)}
      style={{ borderTop: `3px solid ${accent}` }}
    >
      <div className="stat-card-icon" style={{ background: `color-mix(in oklch, ${accent} 16%, var(--surface-container-low))`, color: accent }}>
        {icon}
      </div>
      <div className="t-label mt-3" style={{ color: "var(--on-surface-variant)" }}>
        {label}
      </div>
      <div className="mono mt-1" style={{ fontSize: 26, fontWeight: 500, letterSpacing: "-0.3px" }}>
        {value}
      </div>
      {caption && (
        <div className="t-body-sm mt-1.5" style={{ color: "var(--on-surface-variant)" }}>
          {caption}
        </div>
      )}
    </div>
  );
}

type Variant = "filled" | "outline" | "outline-error" | "text";

export function Button({
  variant = "filled",
  className,
  children,
  ...rest
}: ButtonHTMLAttributes<HTMLButtonElement> & { variant?: Variant }) {
  const variantClass =
    variant === "filled"
      ? "btn-filled"
      : variant === "outline"
        ? "btn-outline"
        : variant === "outline-error"
          ? "btn-outline-error"
          : "btn-text";
  return (
    <button className={cn("btn", variantClass, className)} {...rest}>
      {children}
    </button>
  );
}

export function StatusDot({
  status,
  children,
}: {
  status: string;
  children: React.ReactNode;
}) {
  return (
    <div className={cn("status", status)}>
      <span className="dot" />
      {children}
    </div>
  );
}

export function ConfigPill({
  highlight,
  children,
}: {
  highlight?: boolean;
  children: React.ReactNode;
}) {
  return (
    <span
      className="config-pill"
      title={typeof children === "string" ? children : undefined}
      style={
        highlight
          ? { background: "var(--primary-container)", color: "var(--on-primary-container)" }
          : undefined
      }
    >
      {children}
    </span>
  );
}

export function Filter({
  active,
  onClick,
  children,
}: {
  active?: boolean;
  onClick?: () => void;
  children: React.ReactNode;
}) {
  return (
    <button className={cn("filter", active && "active")} onClick={onClick}>
      {children}
    </button>
  );
}
