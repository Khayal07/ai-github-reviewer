export interface Stats {
  total_reviews: number;
  total_repos: number;
  total_findings: number;
  verdicts: Record<string, number>;
  avg_latency_ms: number | null;
}

export interface ReviewSummary {
  id: number;
  repo_full_name: string;
  pr_number: number;
  head_sha: string | null;
  status: string;
  verdict: string | null;
  counts: Record<string, number>;
  latency_ms: number | null;
  finding_count: number | null;
  created_at: string | null;
}

export interface Finding {
  id: number;
  file: string;
  line: number;
  end_line: number | null;
  side: string;
  severity: string;
  pass_type: string;
  title: string;
  message: string;
  suggestion: string | null;
  confidence: number;
}

export interface ReviewDetail extends ReviewSummary {
  findings: Finding[];
}

export interface Repo {
  id: number | null;
  full_name: string;
  installation_id: number | null;
  review_count: number;
  created_at: string | null;
}

export interface EvalRun {
  id: number;
  num_cases: number;
  recall: number | null;
  precision: number | null;
  avg_latency_ms: number | null;
  report: Record<string, unknown> | null;
  created_at: string | null;
}

async function j<T>(path: string): Promise<T> {
  const res = await fetch(path);
  if (!res.ok) throw new Error(`${res.status} ${res.statusText}`);
  return res.json() as Promise<T>;
}

export const getStats = () => j<Stats>("/api/stats");
export const getReviews = () => j<ReviewSummary[]>("/api/reviews");
export const getReview = (id: number | string) => j<ReviewDetail>(`/api/reviews/${id}`);
export const getRepos = () => j<Repo[]>("/api/repos");
export const getEvalRuns = () => j<EvalRun[]>("/api/eval");
