"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import {
  CostIcon,
  EvaluateIcon,
  ExperimentsIcon,
  OptimizeIcon,
  OverviewIcon,
  SettingsIcon,
} from "./icons";

function railItems(projectId: string) {
  return [
    { href: `/projects/${projectId}`, label: "Overview", Icon: OverviewIcon, exact: true },
    { href: `/projects/${projectId}/cost`, label: "Cost", Icon: CostIcon },
    { href: `/projects/${projectId}/optimizations`, label: "Optimize", Icon: OptimizeIcon },
    { href: `/projects/${projectId}/experiments`, label: "Experiments", Icon: ExperimentsIcon },
    { href: `/projects/${projectId}/evaluations`, label: "Evaluate", Icon: EvaluateIcon },
  ];
}

export function NavRail({ projectId }: { projectId: string }) {
  const pathname = usePathname();
  const items = railItems(projectId);

  return (
    <div className="w-20 shrink-0 bg-(--surface) flex flex-col items-center pt-5 pb-4 gap-2">
      <Link
        href="/projects"
        className="w-8 h-8 rounded-[9px] bg-(--primary) text-(--on-primary) flex items-center justify-center font-bold text-[13px] mb-6 tracking-tight"
      >
        AC
      </Link>

      {items.map(({ href, label, Icon, exact }) => {
        const active = exact ? pathname === href : pathname.startsWith(href);
        return (
          <Link key={href} href={href} className="rail-item">
            <div className={`rail-indicator${active ? " active" : ""}`}>
              <Icon />
            </div>
            <span
              className="t-label"
              style={{
                color: active ? "var(--on-surface)" : "var(--on-surface-variant)",
                fontWeight: active ? 500 : 400,
              }}
            >
              {label}
            </span>
          </Link>
        );
      })}

      <div className="flex-1" />
      <div className="rail-item">
        <div className="rail-indicator">
          <SettingsIcon />
        </div>
      </div>
    </div>
  );
}
