import Link from "next/link";
import {
  CostIcon,
  EvaluateIcon,
  ExperimentsIcon,
  OptimizeIcon,
  OverviewIcon,
  SettingsIcon,
} from "./icons";

// Project-agnostic rail shown on /projects (no project selected yet), so the
// per-project sections (Cost/Optimize/Experiments/Evaluate) render disabled
// rather than linking anywhere.
export function NavRailGlobal() {
  const disabled = [
    { label: "Cost", Icon: CostIcon },
    { label: "Optimize", Icon: OptimizeIcon },
    { label: "Experiments", Icon: ExperimentsIcon },
    { label: "Evaluate", Icon: EvaluateIcon },
  ];

  return (
    <div className="w-20 shrink-0 bg-(--surface) flex flex-col items-center pt-5 pb-4 gap-2">
      <Link
        href="/projects"
        className="w-8 h-8 rounded-[9px] bg-(--primary) text-(--on-primary) flex items-center justify-center font-bold text-[13px] mb-6 tracking-tight"
      >
        AC
      </Link>

      <div className="rail-item">
        <div className="rail-indicator active">
          <OverviewIcon />
        </div>
        <span className="t-label" style={{ color: "var(--on-surface)" }}>
          Projects
        </span>
      </div>

      {disabled.map(({ label, Icon }) => (
        <div className="rail-item" key={label} style={{ cursor: "default", opacity: 0.45 }}>
          <div className="rail-indicator">
            <Icon />
          </div>
          <span className="t-label" style={{ color: "var(--on-surface-variant)", fontWeight: 400 }}>
            {label}
          </span>
        </div>
      ))}

      <div className="flex-1" />
      {/* Settings is per-project (Langfuse keys, appearance) - no project is
          selected here, so this stays visibly inert rather than a dead link. */}
      <div className="rail-item" style={{ cursor: "default", opacity: 0.45 }}>
        <div className="rail-indicator">
          <SettingsIcon />
        </div>
      </div>
    </div>
  );
}
