import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import * as api from "./api";
import type { GroupBy, ProjectUpdate, RecommendationStatus } from "./types";

export function useProjects() {
  return useQuery({ queryKey: ["projects"], queryFn: api.listProjects });
}

export function useProject(id: string) {
  return useQuery({ queryKey: ["projects", id], queryFn: () => api.getProject(id) });
}

export function useUpdateProject(id: string) {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (payload: ProjectUpdate) => api.updateProject(id, payload),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["projects", id] });
      qc.invalidateQueries({ queryKey: ["projects"] });
    },
  });
}

export function useProjectCost(
  projectId: string,
  fromTs: string,
  toTs: string,
  groupBy?: GroupBy,
) {
  return useQuery({
    queryKey: ["cost", projectId, fromTs, toTs, groupBy ?? "none"],
    queryFn: () => api.getProjectCost(projectId, fromTs, toTs, groupBy),
    enabled: Boolean(projectId),
  });
}

export function useOptimizations(projectId: string) {
  return useQuery({
    queryKey: ["optimizations", projectId],
    queryFn: () => api.listOptimizations(projectId),
    enabled: Boolean(projectId),
  });
}

export function useAnalyzeOptimizations(projectId: string) {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: ({ fromTs, toTs }: { fromTs: string; toTs: string }) =>
      api.analyzeOptimizations(projectId, fromTs, toTs),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["optimizations", projectId] });
    },
  });
}

export function useUpdateOptimizationStatus(projectId: string) {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: ({
      recommendationId,
      status,
    }: {
      recommendationId: string;
      status: RecommendationStatus;
    }) => api.updateOptimizationStatus(projectId, recommendationId, status),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["optimizations", projectId] });
    },
  });
}

export function useEvaluations(projectId: string) {
  return useQuery({
    queryKey: ["evaluations", projectId],
    queryFn: () => api.listEvaluations(projectId),
    enabled: Boolean(projectId),
  });
}

export function useImportEvaluationDataset(projectId: string) {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (payload: Parameters<typeof api.importEvaluationDataset>[1]) =>
      api.importEvaluationDataset(projectId, payload),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["evaluations", projectId] });
    },
  });
}

export function useExperiments(projectId: string) {
  return useQuery({
    queryKey: ["experiments", projectId],
    queryFn: () => api.listExperiments(projectId),
    enabled: Boolean(projectId),
  });
}

export function useExperiment(projectId: string, experimentId: string) {
  return useQuery({
    queryKey: ["experiments", projectId, experimentId],
    queryFn: () => api.getExperiment(projectId, experimentId),
    enabled: Boolean(projectId && experimentId),
  });
}

export function useExperimentRuns(projectId: string, experimentId: string) {
  return useQuery({
    queryKey: ["experiments", projectId, experimentId, "runs"],
    queryFn: () => api.listExperimentRuns(projectId, experimentId),
    enabled: Boolean(projectId && experimentId),
  });
}

export function useCreateExperiment(projectId: string) {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (payload: Parameters<typeof api.createExperiment>[1]) =>
      api.createExperiment(projectId, payload),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["experiments", projectId] });
      qc.invalidateQueries({ queryKey: ["optimizations", projectId] });
    },
  });
}

export function useRunExperiment(projectId: string, experimentId: string) {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: () => api.runExperiment(projectId, experimentId),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["experiments", projectId, experimentId] });
      qc.invalidateQueries({ queryKey: ["experiments", projectId] });
    },
  });
}
