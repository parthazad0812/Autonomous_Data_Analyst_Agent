// ── Auth types ────────────────────────────────────────────────────────────────

export interface User {
  id: string;
  email: string;
  full_name: string | null;
  created_at: string;
}

export interface AuthToken {
  access_token: string;
  token_type: string;
  user: User;
}

// ── Session types ─────────────────────────────────────────────────────────────

export type SessionStatus = "pending" | "running" | "completed" | "failed";

export interface AnalysisSession {
  id: string;
  user_id: string;
  title: string | null;
  status: SessionStatus;
  dataset_filename: string;
  dataset_rows: number | null;
  dataset_columns: number | null;
  user_query: string | null;
  created_at: string;
  completed_at: string | null;
  total_llm_cost: number;
  total_llm_tokens: number;
}

export interface SessionListResponse {
  sessions: AnalysisSession[];
  total: number;
}
