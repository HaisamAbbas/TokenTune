// Types mirroring backend/app/schemas/*.py response shapes.

export interface Project {
  id: string;
  name: string;
  slug: string;
  created_at: string;
  langfuse_configured: boolean;
}

export interface ProjectUpdate {
  name?: string;
  langfuse_public_key?: string;
  langfuse_secret_key?: string;
}

export interface ProjectMetrics {
  total_spend: number;
  total_potential_savings_low: number;
  total_potential_savings_high: number;
  open_opportunity_count: number;
}

export type GroupBy = "day" | "model" | "workflow";

export interface CostBucket {
  bucket: string | null;
  total_cost: number | null;
  total_input_tokens: number;
  total_output_tokens: number;
  total_tokens: number;
  avg_latency_ms: number | null;
  request_count: number;
}

export type RuleName =
  | "excessive_retrieval_context"
  | "model_cost_optimization"
  | "prompt_optimization"
  | "unnecessary_generation_calls"
  | "segmented_model_routing";

// "experiment_created"/"experiment_running"/"validated" are set
// automatically by the backend as an experiment's lifecycle advances - only
// "adopted"/"rejected" are ever set by a manual PATCH from the frontend.
export type RecommendationStatus =
  | "pending"
  | "experiment_created"
  | "experiment_running"
  | "validated"
  | "adopted"
  | "rejected";

export type ConfidenceBucket = "high" | "medium" | "low";

export interface RecommendationEvidence {
  sample_size: number;
  avg_input_tokens: number;
  p95_input_tokens: number | null;
  current_value: unknown;
  ratio: number | null;
  estimated_monthly_cost: number;
  quality_evidence: "not_yet_tested" | "validated";
  recommended_next_step: string;
  estimated_savings_low?: number;
  estimated_savings_high?: number;
}

export interface OptimizationRecommendation {
  id: string;
  project_id: string;
  workflow: string | null;
  environment_id: string | null;
  rule_name: RuleName;
  reason: string;
  current_config: Record<string, unknown>;
  proposed_config: Record<string, unknown>;
  estimated_cost_impact: string;
  required_experiment: Record<string, unknown>;
  experiment_id: string | null;
  confidence: number;
  confidence_bucket: ConfidenceBucket | null;
  evidence: RecommendationEvidence | null;
  estimated_savings_low: number | null;
  estimated_savings_high: number | null;
  status: RecommendationStatus;
  created_at: string;
}

export interface AnalyzeResult {
  recommendations_created: number;
  recommendations: OptimizationRecommendation[];
}

export type ExperimentStatus = "pending" | "running" | "completed" | "failed";
export type Variant = "baseline" | "experiment";
// "fallback" = the platform's own AnswerCorrectnessEvaluator (always
// available); "deepeval" = DeepEval-backed, requires evaluator_metrics.
export type EvaluatorType = "fallback" | "deepeval";

export interface Experiment {
  id: string;
  project_id: string;
  recommendation_id: string | null;
  name: string;
  baseline_config: Record<string, unknown>;
  experiment_config: Record<string, unknown>;
  evaluation_dataset_id: string;
  evaluator_type: EvaluatorType;
  evaluator_metrics: string[] | null;
  status: ExperimentStatus;
  error: string | null;
  created_at: string;
}

export interface ExperimentRunMetrics {
  cost_per_request: number;
  total_cost: number;
  avg_input_tokens: number;
  avg_output_tokens: number;
  avg_latency_ms: number;
  // One entry per metric the experiment's evaluator computed (e.g.
  // {"correctness": 0.9} for the fallback evaluator, or
  // {"faithfulness": 0.94, "answer_relevancy": 0.92} for a DeepEval-backed
  // experiment with multiple metrics selected).
  quality_scores: Record<string, number>;
  request_count: number;
  failed_questions?: string[];
}

export interface ExperimentRun {
  id: string;
  experiment_id: string;
  variant: Variant;
  metrics: ExperimentRunMetrics;
  started_at: string;
  completed_at: string | null;
}

export interface ExperimentComparisonResult {
  experiment: Experiment;
  baseline_run: ExperimentRun;
  experiment_run: ExperimentRun;
  cost_reduction_pct: number;
  quality_differences: Record<string, number>;
  latency_difference_ms: number;
  token_reduction_pct: number;
  failed_questions: string[];
}

export interface EvaluationDataset {
  id: string;
  project_id: string;
  name: string;
  description: string | null;
  created_at: string;
}

export interface EvaluationDatasetImportResult {
  dataset: EvaluationDataset;
  items_created: number;
}

export interface EvaluationItemImport {
  question: string;
  expected_answer: string;
  source_doc?: string | null;
}
