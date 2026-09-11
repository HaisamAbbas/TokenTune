"use client";

import { useParams } from "next/navigation";
import { useState } from "react";
import { TopBar } from "@/components/top-bar";
import { Button, Panel } from "@/components/ui";
import { useProject, useUpdateProject } from "@/lib/queries";
import { type ThemePreference, useThemePreference } from "@/lib/theme";

const inputStyle: React.CSSProperties = {
  background: "var(--surface-container-high)",
  border: "none",
  borderRadius: 10,
  padding: "10px 12px",
  color: "var(--on-surface)",
};

const THEME_OPTIONS: { value: ThemePreference; label: string }[] = [
  { value: "system", label: "System" },
  { value: "light", label: "Light" },
  { value: "dark", label: "Dark" },
];

export default function SettingsPage() {
  const { id } = useParams<{ id: string }>();
  const { data: project } = useProject(id);
  const [theme, setTheme] = useThemePreference();

  return (
    <>
      <TopBar title="Settings" subtitle={project?.slug} />

      <div className="flex-1 overflow-auto px-7 pb-7 flex flex-col gap-5" style={{ maxWidth: 640 }}>
        <Panel className="p-6 flex flex-col gap-4">
          <div className="t-title">Appearance</div>
          <div className="t-body-sm" style={{ color: "var(--on-surface-variant)" }}>
            Applies to this browser only.
          </div>
          <div className="flex gap-2">
            {THEME_OPTIONS.map((option) => (
              <button
                key={option.value}
                type="button"
                className={`filter${theme === option.value ? " active" : ""}`}
                onClick={() => setTheme(option.value)}
              >
                {option.label}
              </button>
            ))}
          </div>
        </Panel>

        <LangfusePanel projectId={id} langfuseConfigured={project?.langfuse_configured ?? false} />
      </div>
    </>
  );
}

function LangfusePanel({
  projectId,
  langfuseConfigured,
}: {
  projectId: string;
  langfuseConfigured: boolean;
}) {
  const updateProject = useUpdateProject(projectId);
  const [publicKey, setPublicKey] = useState("");
  const [secretKey, setSecretKey] = useState("");

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    await updateProject.mutateAsync({
      langfuse_public_key: publicKey,
      langfuse_secret_key: secretKey,
    });
    setPublicKey("");
    setSecretKey("");
  }

  return (
    <Panel className="p-6 flex flex-col gap-4">
      <div className="flex items-center justify-between">
        <div className="t-title">Langfuse integration</div>
        <div
          className="status"
          style={{ color: langfuseConfigured ? "var(--success)" : "var(--on-surface-variant)" }}
        >
          <span
            className="dot"
            style={{ background: langfuseConfigured ? "var(--success)" : "var(--on-surface-variant)" }}
          />
          {langfuseConfigured ? "Configured" : "Not configured"}
        </div>
      </div>
      <div className="t-body-sm" style={{ color: "var(--on-surface-variant)" }}>
        Used to pull telemetry via the Langfuse adapter. Keys are stored write-only — they are
        never returned by the API once saved.
      </div>

      <form onSubmit={handleSubmit} className="flex flex-col gap-4">
        <div className="flex flex-col gap-1.5">
          <label className="t-label" style={{ color: "var(--on-surface-variant)" }}>
            PUBLIC KEY
          </label>
          <input
            value={publicKey}
            onChange={(e) => setPublicKey(e.target.value)}
            placeholder={langfuseConfigured ? "•••••••• (unchanged)" : "pk-lf-..."}
            className="t-body mono"
            style={inputStyle}
          />
        </div>
        <div className="flex flex-col gap-1.5">
          <label className="t-label" style={{ color: "var(--on-surface-variant)" }}>
            SECRET KEY
          </label>
          <input
            type="password"
            value={secretKey}
            onChange={(e) => setSecretKey(e.target.value)}
            placeholder={langfuseConfigured ? "•••••••• (unchanged)" : "sk-lf-..."}
            className="t-body mono"
            style={inputStyle}
          />
        </div>

        {updateProject.isError && (
          <span className="t-body-sm" style={{ color: "var(--error)" }}>
            {(updateProject.error as Error).message}
          </span>
        )}
        {updateProject.isSuccess && (
          <span className="t-body-sm" style={{ color: "var(--success)" }}>
            Saved.
          </span>
        )}

        <div className="flex justify-end">
          <Button type="submit" disabled={updateProject.isPending || (!publicKey && !secretKey)}>
            {updateProject.isPending ? "Saving…" : "Save"}
          </Button>
        </div>
      </form>
    </Panel>
  );
}
