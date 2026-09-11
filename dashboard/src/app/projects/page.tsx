"use client";

import Link from "next/link";
import { NavRailGlobal } from "@/components/nav-rail-global";
import { TopBar } from "@/components/top-bar";
import { Panel } from "@/components/ui";
import { useProjects } from "@/lib/queries";

export default function ProjectsPage() {
  const { data: projects, isLoading, isError, error } = useProjects();

  return (
    <div style={{ display: "flex", height: "100vh", overflow: "hidden" }}>
      <NavRailGlobal />
      <div className="flex-1 flex flex-col min-w-0 bg-(--surface)">
        <TopBar title="Projects" subtitle={projects ? `${projects.length} total` : undefined} />

        <div className="flex-1 overflow-auto px-7 pb-7 flex flex-col gap-5">
          <Panel className="overflow-hidden">
            {isLoading && (
              <div className="row" style={{ color: "var(--on-surface-variant)" }}>
                Loading projects…
              </div>
            )}
            {isError && (
              <div className="row t-body-sm" style={{ color: "var(--error)" }}>
                Failed to load projects: {(error as Error).message}
              </div>
            )}
            {projects?.length === 0 && (
              <div className="row t-body-sm" style={{ color: "var(--on-surface-variant)" }}>
                No projects yet.
              </div>
            )}
            {projects?.map((p) => (
              <Link key={p.id} href={`/projects/${p.id}`} className="row" style={{ color: "inherit" }}>
                <div style={{ flex: 1, minWidth: 0 }}>
                  <div className="t-body" style={{ fontWeight: 500 }}>
                    {p.name}
                  </div>
                  <div className="t-body-sm mono" style={{ color: "var(--on-surface-variant)" }}>
                    {p.slug}
                  </div>
                </div>
                <div className="t-body-sm" style={{ color: "var(--on-surface-variant)", flexShrink: 0 }}>
                  created {new Date(p.created_at).toLocaleDateString()}
                </div>
              </Link>
            ))}
          </Panel>
        </div>
      </div>
    </div>
  );
}
