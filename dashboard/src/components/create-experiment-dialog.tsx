"use client";

import { useRouter } from "next/navigation";
import { useState } from "react";
import { Dialog } from "./dialog";
import { Button } from "./ui";
import { useCreateExperiment, useEvaluations } from "@/lib/queries";
import type { OptimizationRecommendation } from "@/lib/types";

export function CreateExperimentDialog({
  projectId,
  recommendation,
  open,
  onOpenChange,
}: {
  projectId: string;
  recommendation: OptimizationRecommendation | null;
  open: boolean;
  onOpenChange: (open: boolean) => void;
}) {
  const router = useRouter();
  const { data: datasets } = useEvaluations(projectId);
  const createExperiment = useCreateExperiment(projectId);

  const [name, setName] = useState("");
  const [datasetId, setDatasetId] = useState("");

  if (!recommendation) return null;

  const effectiveName = name || `${recommendation.rule_name.replaceAll("_", "-")}-experiment`;

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    if (!datasetId || !recommendation) return;
    const experiment = await createExperiment.mutateAsync({
      recommendation_id: recommendation.id,
      name: effectiveName,
      baseline_config: recommendation.current_config,
      experiment_config: recommendation.proposed_config,
      evaluation_dataset_id: datasetId,
    });
    onOpenChange(false);
    router.push(`/projects/${projectId}/experiments/${experiment.id}`);
  }

  return (
    <Dialog open={open} onOpenChange={onOpenChange} title="Create experiment">
      <form onSubmit={handleSubmit} className="flex flex-col gap-4">
        <div className="flex flex-col gap-1.5">
          <label className="t-label" style={{ color: "var(--on-surface-variant)" }}>
            NAME
          </label>
          <input
            className="t-body"
            placeholder={effectiveName}
            value={name}
            onChange={(e) => setName(e.target.value)}
            style={{
              background: "var(--surface-container-high)",
              border: "none",
              borderRadius: 10,
              padding: "10px 12px",
              color: "var(--on-surface)",
            }}
          />
        </div>

        <div className="flex gap-3">
          <div className="flex-1 flex flex-col gap-1.5">
            <span className="t-label" style={{ color: "var(--on-surface-variant)" }}>
              BASELINE CONFIG
            </span>
            <div className="config-pill mono t-body-sm" style={{ whiteSpace: "pre-wrap" }}>
              {JSON.stringify(recommendation.current_config)}
            </div>
          </div>
          <div className="flex-1 flex flex-col gap-1.5">
            <span className="t-label" style={{ color: "var(--on-surface-variant)" }}>
              EXPERIMENT CONFIG
            </span>
            <div
              className="config-pill mono t-body-sm"
              style={{
                whiteSpace: "pre-wrap",
                background: "var(--primary-container)",
                color: "var(--on-primary-container)",
              }}
            >
              {JSON.stringify(recommendation.proposed_config)}
            </div>
          </div>
        </div>

        <div className="flex flex-col gap-1.5">
          <label className="t-label" style={{ color: "var(--on-surface-variant)" }}>
            EVALUATION DATASET
          </label>
          <select
            required
            value={datasetId}
            onChange={(e) => setDatasetId(e.target.value)}
            className="t-body"
            style={{
              background: "var(--surface-container-high)",
              border: "none",
              borderRadius: 10,
              padding: "10px 12px",
              color: "var(--on-surface)",
            }}
          >
            <option value="" disabled>
              Select a dataset…
            </option>
            {datasets?.map((d) => (
              <option key={d.id} value={d.id}>
                {d.name}
              </option>
            ))}
          </select>
          {datasets?.length === 0 && (
            <span className="t-body-sm" style={{ color: "var(--on-surface-variant)" }}>
              No evaluation datasets yet — import one from the Evaluate tab first.
            </span>
          )}
        </div>

        {createExperiment.isError && (
          <span className="t-body-sm" style={{ color: "var(--error)" }}>
            {(createExperiment.error as Error).message}
          </span>
        )}

        <div className="flex justify-end gap-2 mt-2">
          <Button type="button" variant="outline" onClick={() => onOpenChange(false)}>
            Cancel
          </Button>
          <Button type="submit" disabled={!datasetId || createExperiment.isPending}>
            {createExperiment.isPending ? "Creating…" : "Create experiment"}
          </Button>
        </div>
      </form>
    </Dialog>
  );
}
