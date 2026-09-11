"use client";

import { useParams } from "next/navigation";
import { useState } from "react";
import { Dialog } from "@/components/dialog";
import { TopBar } from "@/components/top-bar";
import { Button, Panel } from "@/components/ui";
import { useEvaluations, useImportEvaluationDataset, useProject } from "@/lib/queries";

export default function EvaluationsPage() {
  const { id } = useParams<{ id: string }>();
  const { data: project } = useProject(id);
  const { data: datasets, isLoading } = useEvaluations(id);
  const [importOpen, setImportOpen] = useState(false);

  return (
    <>
      <TopBar
        title="Evaluations"
        subtitle={project?.slug}
        action={<Button variant="outline" onClick={() => setImportOpen(true)}>Import dataset</Button>}
      />

      <div className="flex-1 overflow-auto px-7 pb-7 flex flex-col gap-4">
        <Panel className="overflow-hidden">
          {isLoading && (
            <div className="row t-body-sm" style={{ color: "var(--on-surface-variant)", borderTop: "none" }}>
              Loading…
            </div>
          )}
          {!isLoading && datasets?.length === 0 && (
            <div className="row t-body-sm" style={{ color: "var(--on-surface-variant)", borderTop: "none" }}>
              No evaluation datasets yet.
            </div>
          )}
          {datasets?.map((d) => (
            <div key={d.id} className="row">
              <div style={{ flex: 1, minWidth: 0 }}>
                <div className="t-body" style={{ fontWeight: 500 }}>
                  {d.name}
                </div>
                <div className="t-body-sm" style={{ color: "var(--on-surface-variant)" }}>
                  {d.description ?? "—"}
                </div>
              </div>
              <div className="t-body-sm" style={{ color: "var(--on-surface-variant)", width: 160, flexShrink: 0, textAlign: "right" }}>
                {new Date(d.created_at).toLocaleDateString()}
              </div>
            </div>
          ))}
        </Panel>
      </div>

      <ImportDatasetDialog projectId={id} open={importOpen} onOpenChange={setImportOpen} />
    </>
  );
}

function ImportDatasetDialog({
  projectId,
  open,
  onOpenChange,
}: {
  projectId: string;
  open: boolean;
  onOpenChange: (open: boolean) => void;
}) {
  const importDataset = useImportEvaluationDataset(projectId);
  const [name, setName] = useState("");
  const [description, setDescription] = useState("");
  const [itemsJson, setItemsJson] = useState(
    '[\n  {"question": "...", "expected_answer": "..."}\n]',
  );
  const [parseError, setParseError] = useState<string | null>(null);

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    setParseError(null);
    let items;
    try {
      items = JSON.parse(itemsJson);
      if (!Array.isArray(items)) throw new Error("items must be a JSON array");
    } catch (err) {
      setParseError((err as Error).message);
      return;
    }
    await importDataset.mutateAsync({ name, description: description || null, items });
    onOpenChange(false);
    setName("");
    setDescription("");
    setItemsJson('[\n  {"question": "...", "expected_answer": "..."}\n]');
  }

  return (
    <Dialog open={open} onOpenChange={onOpenChange} title="Import evaluation dataset">
      <form onSubmit={handleSubmit} className="flex flex-col gap-4">
        <div className="flex flex-col gap-1.5">
          <label className="t-label" style={{ color: "var(--on-surface-variant)" }}>
            NAME
          </label>
          <input
            required
            value={name}
            onChange={(e) => setName(e.target.value)}
            className="t-body"
            style={{ background: "var(--surface-container-high)", border: "none", borderRadius: 10, padding: "10px 12px", color: "var(--on-surface)" }}
          />
        </div>
        <div className="flex flex-col gap-1.5">
          <label className="t-label" style={{ color: "var(--on-surface-variant)" }}>
            DESCRIPTION (OPTIONAL)
          </label>
          <input
            value={description}
            onChange={(e) => setDescription(e.target.value)}
            className="t-body"
            style={{ background: "var(--surface-container-high)", border: "none", borderRadius: 10, padding: "10px 12px", color: "var(--on-surface)" }}
          />
        </div>
        <div className="flex flex-col gap-1.5">
          <label className="t-label" style={{ color: "var(--on-surface-variant)" }}>
            ITEMS (JSON ARRAY OF question/expected_answer)
          </label>
          <textarea
            required
            rows={8}
            value={itemsJson}
            onChange={(e) => setItemsJson(e.target.value)}
            className="mono t-body-sm"
            style={{ background: "var(--surface-container-high)", border: "none", borderRadius: 10, padding: "10px 12px", color: "var(--on-surface)" }}
          />
          {parseError && (
            <span className="t-body-sm" style={{ color: "var(--error)" }}>
              {parseError}
            </span>
          )}
        </div>

        {importDataset.isError && (
          <span className="t-body-sm" style={{ color: "var(--error)" }}>
            {(importDataset.error as Error).message}
          </span>
        )}

        <div className="flex justify-end gap-2 mt-2">
          <Button type="button" variant="outline" onClick={() => onOpenChange(false)}>
            Cancel
          </Button>
          <Button type="submit" disabled={importDataset.isPending}>
            {importDataset.isPending ? "Importing…" : "Import"}
          </Button>
        </div>
      </form>
    </Dialog>
  );
}
