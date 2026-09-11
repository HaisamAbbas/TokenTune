import type {
  AnalyzeResult,
  CostBucket,
  EvaluationDataset,
  EvaluationDatasetImportResult,
  EvaluationItemImport,
  Experiment,
  ExperimentComparisonResult,
  ExperimentRun,
  GroupBy,
  OptimizationRecommendation,
  Project,
  ProjectMetrics,
  ProjectUpdate,
  RecommendationStatus,
} from "./types";

const BASE_URL = process.env.NEXT_PUBLIC_API_BASE_URL ?? "http://localhost:8000";

export class ApiError extends Error {
  status: number;
  constructor(status: number, message: string) {
    super(message);
    this.status = status;
    this.name = "ApiError";
  }
}

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const res = await fetch(`${BASE_URL}${path}`, {
    ...init,
    headers: {
      "Content-Type": "application/json",
      ...init?.headers,
    },
  });
  if (!res.ok) {
    let detail = res.statusText;
    try {
      const body = await res.json();
      detail = body.detail ?? detail;
    } catch {
      // ignore parse failure, fall back to statusText
    }
    throw new ApiError(res.status, typeof detail === "string" ? detail : JSON.stringify(detail));
  }
  if (res.status === 204) return undefined as T;
  return res.json() as Promise<T>;
}

// Projects

export const listProjects = () => request<Project[]>("/projects");
export const getProject = (id: string) => request<Project>(`/projects/${id}`);
export const createProject = (payload: { name: string; slug: string }) =>
  request<Project>("/projects", { method: "POST", body: JSON.stringify(payload) });
export const updateProject = (id: string, payload: ProjectUpdate) =>
  request<Project>(`/projects/${id}`, { method: "PATCH", body: JSON.stringify(payload) });

// Cost

export const getProjectCost = (
  projectId: string,
  fromTs: string,
  toTs: string,
  groupBy?: GroupBy,
) => {
  const params = new URLSearchParams({ from_ts: fromTs, to_ts: toTs });
  if (groupBy) params.set("group_by", groupBy);
  return request<CostBucket[]>(`/projects/${projectId}/cost?${params.toString()}`);
};

export const getProjectMetrics = (projectId: string, fromTs: string, toTs: string) => {
  const params = new URLSearchParams({ from_ts: fromTs, to_ts: toTs });
  return request<ProjectMetrics>(`/projects/${projectId}/metrics?${params.toString()}`);
};

// Optimizations

export const listOptimizations = (projectId: string) =>
  request<OptimizationRecommendation[]>(`/projects/${projectId}/optimizations`);

export const analyzeOptimizations = (projectId: string, fromTs: string, toTs: string) =>
  request<AnalyzeResult>(`/projects/${projectId}/optimizations/analyze`, {
    method: "POST",
    body: JSON.stringify({ from_ts: fromTs, to_ts: toTs }),
  });

export const updateOptimizationStatus = (
  projectId: string,
  recommendationId: string,
  status: RecommendationStatus,
) =>
  request<OptimizationRecommendation>(
    `/projects/${projectId}/optimizations/${recommendationId}`,
    { method: "PATCH", body: JSON.stringify({ status }) },
  );

// Evaluations

export const listEvaluations = (projectId: string) =>
  request<EvaluationDataset[]>(`/projects/${projectId}/evaluations`);

export const importEvaluationDataset = (
  projectId: string,
  payload: { name: string; description?: string | null; items: EvaluationItemImport[] },
) =>
  request<EvaluationDatasetImportResult>(`/projects/${projectId}/evaluations/import`, {
    method: "POST",
    body: JSON.stringify(payload),
  });

// Experiments

export const listExperiments = (projectId: string) =>
  request<Experiment[]>(`/projects/${projectId}/experiments`);

export const getExperiment = (projectId: string, experimentId: string) =>
  request<Experiment>(`/projects/${projectId}/experiments/${experimentId}`);

export const listExperimentRuns = (projectId: string, experimentId: string) =>
  request<ExperimentRun[]>(`/projects/${projectId}/experiments/${experimentId}/runs`);

export const createExperiment = (
  projectId: string,
  payload: {
    recommendation_id?: string | null;
    name: string;
    baseline_config: Record<string, unknown>;
    experiment_config: Record<string, unknown>;
    evaluation_dataset_id: string;
  },
) =>
  request<Experiment>(`/projects/${projectId}/experiments`, {
    method: "POST",
    body: JSON.stringify(payload),
  });

export const runExperiment = (projectId: string, experimentId: string) =>
  request<ExperimentComparisonResult>(
    `/projects/${projectId}/experiments/${experimentId}/run`,
    { method: "POST" },
  );
