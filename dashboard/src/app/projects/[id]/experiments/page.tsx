"use client";

import Link from "next/link";
import { useParams } from "next/navigation";
import { TopBar } from "@/components/top-bar";
import { Panel, StatusDot } from "@/components/ui";
import { useExperiments, useProject } from "@/lib/queries";

export default function ExperimentsPage() {
  const { id } = useParams<{ id: string }>();
  const { data: project } = useProject(id);
  const { data: experiments, isLoading } = useExperiments(id);

  const sorted = [...(experiments ?? [])].sort((a, b) => (a.created_at < b.created_at ? 1 : -1));

  return (
    <>
      <TopBar title="Experiments" subtitle={project?.slug} />

      <div className="flex-1 overflow-auto px-7 pb-7 flex flex-col gap-4">
        <Panel className="overflow-hidden">
          {isLoading && (
            <div className="row t-body-sm" style={{ color: "var(--on-surface-variant)", borderTop: "none" }}>
              Loading…
            </div>
          )}
          {!isLoading && sorted.length === 0 && (
            <div className="row t-body-sm" style={{ color: "var(--on-surface-variant)", borderTop: "none" }}>
              No experiments yet — create one from a recommendation on the Optimize tab.
            </div>
          )}
          {sorted.map((exp) => (
            <Link key={exp.id} href={`/projects/${id}/experiments/${exp.id}`} className="row" style={{ color: "inherit" }}>
              <div style={{ flex: 1, minWidth: 0 }}>
                <div className="t-body" style={{ fontWeight: 500 }}>
                  {exp.name}
                </div>
                <div className="t-body-sm mono" style={{ color: "var(--on-surface-variant)" }}>
                  {JSON.stringify(exp.baseline_config)} → {JSON.stringify(exp.experiment_config)}
                </div>
              </div>
              <div style={{ width: 140, flexShrink: 0 }}>
                <StatusDot status={exp.status}>{exp.status[0].toUpperCase() + exp.status.slice(1)}</StatusDot>
              </div>
              <div className="t-body-sm" style={{ color: "var(--on-surface-variant)", width: 160, flexShrink: 0, textAlign: "right" }}>
                {new Date(exp.created_at).toLocaleDateString()}
              </div>
            </Link>
          ))}
        </Panel>
      </div>
    </>
  );
}
