const BASE = "/api/v1";

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const res = await fetch(`${BASE}${path}`, {
    headers: { "Content-Type": "application/json", ...init?.headers },
    ...init,
  });
  if (!res.ok) {
    const body = await res.text();
    throw new Error(`API ${res.status}: ${body}`);
  }
  if (res.status === 204) return undefined as T;
  return res.json();
}

export interface Contract {
  id: string;
  contract_id: string;
  title: string;
  description: string | null;
  file_path: string;
  owner_team: string | null;
  enforcement_mode: string;
  is_active: boolean;
  created_at: string;
  updated_at: string;
}

export interface ContractDetail extends Contract {
  raw_yaml: string;
}

export interface ValidationRun {
  id: string;
  contract_id: string;
  status: string;
  enforcement_mode: string;
  checks_total: number;
  checks_passed: number;
  checks_failed: number;
  failures: { check: string; field: string; message: string }[] | null;
  server: string | null;
  triggered_by: string | null;
  duration_ms: number | null;
  run_at: string;
}

export interface DriftMetric {
  id: string;
  contract_id: string;
  metric_type: string;
  table_name: string;
  column_name: string | null;
  value: number;
  warning_threshold: number | null;
  breach_threshold: number | null;
  is_warning: boolean;
  is_breached: boolean;
  measured_at: string;
}

export interface DriftAlert {
  contract_id: string;
  metric_type: string;
  table_name: string;
  column_name: string | null;
  current_value: number;
  warning_threshold: number | null;
  breach_threshold: number | null;
  trend_slope: number | null;
  estimated_breach_in_runs: number | null;
}

export interface TeamWithScore {
  id: string;
  name: string;
  current_score: number | null;
  contracts_owned: number;
  violations_30d: number;
}

export interface LeaderboardEntry {
  rank: number;
  team_name: string;
  team_id: string;
  score: number;
  contracts_owned: number;
  violations_30d: number;
}

export interface GraphNode {
  id: string;
  label: string;
  owner_team: string | null;
  status: string;
}

export interface GraphEdge {
  source: string;
  target: string;
  shared_fields: string[];
}

export interface RunSummaryItem {
  contract_id: string;
  total_runs: number;
  passed: number;
  failed: number;
  error: number;
}

export const api = {
  contracts: {
    list: () => request<{ items: Contract[]; total: number }>("/contracts"),
    get: (id: string) => request<ContractDetail>(`/contracts/${id}`),
    create: (data: Record<string, unknown>) =>
      request<Contract>("/contracts", { method: "POST", body: JSON.stringify(data) }),
    triggerRun: (id: string) =>
      request<ValidationRun>(`/contracts/${id}/run`, { method: "POST" }),
  },
  runs: {
    list: (params?: { contract_id?: string; limit?: number; offset?: number }) => {
      const qs = new URLSearchParams();
      if (params?.contract_id) qs.set("contract_id", params.contract_id);
      if (params?.limit) qs.set("limit", String(params.limit));
      if (params?.offset) qs.set("offset", String(params.offset));
      const q = qs.toString();
      return request<{ items: ValidationRun[]; total: number }>(`/runs${q ? `?${q}` : ""}`);
    },
    summary: () => request<{ items: RunSummaryItem[] }>("/runs/summary"),
    get: (id: string) => request<ValidationRun>(`/runs/${id}`),
  },
  drift: {
    status: (contractId: string) => request<DriftMetric[]>(`/drift/${contractId}`),
    history: (contractId: string) =>
      request<{ items: DriftMetric[] }>(`/drift/${contractId}/history`),
    alerts: () => request<DriftAlert[]>("/drift/alerts"),
  },
  compliance: {
    teams: () => request<TeamWithScore[]>("/compliance/teams"),
    leaderboard: () => request<{ items: LeaderboardEntry[] }>("/compliance/leaderboard"),
  },
  impact: {
    graph: () => request<{ nodes: GraphNode[]; edges: GraphEdge[] }>("/impact/graph"),
    downstream: (id: string) =>
      request<{ contract_id: string; downstream: string[] }>(`/impact/${id}/downstream`),
    analyze: (id: string, fields: string[]) =>
      request<{
        contract_id: string;
        changed_fields: string[];
        directly_affected: string[];
        transitively_affected: string[];
        severity: string;
      }>(`/impact/${id}/analyze`, {
        method: "POST",
        body: JSON.stringify({ changed_fields: fields }),
      }),
  },
};
