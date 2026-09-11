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
