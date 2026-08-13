"""
AnalysisState — the shared TypedDict passed between every LangGraph node.
Each agent reads relevant fields and writes its outputs back into state.
"""
from typing import TypedDict, Any


class AgentStepRecord(TypedDict):
    agent_name: str
    step_index: int
    status: str           # running | completed | failed | skipped
    message: str
    code_executed: str
    code_output: str
    error_message: str
    duration_seconds: float
    output_data: dict


class FindingRecord(TypedDict):
    finding_id: str
    agent_name: str
    finding_type: str     # profile | correlation | distribution | outlier | pattern | hypothesis | visualization | report
    title: str
    description: str
    evidence: dict
    confidence: str       # high | medium | low
    hypothesis: str
    visualization_path: str


class AnalysisState(TypedDict):
    # ── Identity ──────────────────────────────────────────────────────────────
    session_id: str
    user_query: str
    dataset_filename: str

    # ── Dataset access ────────────────────────────────────────────────────────
    dataset_minio_path: str   # e.g. "datasets/{session_id}/abc.csv"
    dataset_profile: dict     # from Phase 3 profiler (shape, dtypes, sample)

    # ── Analysis plan (set by Orchestrator) ──────────────────────────────────
    analysis_plan: dict

    # ── Accumulated findings across all agents ───────────────────────────────
    findings: list[FindingRecord]

    # ── Chart paths stored in MinIO ───────────────────────────────────────────
    chart_paths: list[str]

    # ── Final report ──────────────────────────────────────────────────────────
    report_markdown: str

    # ── Execution bookkeeping ─────────────────────────────────────────────────
    step_records: list[AgentStepRecord]
    error_count: int
    current_agent: str

    # ── LLM metadata ──────────────────────────────────────────────────────────
    total_llm_tokens: int
    total_llm_cost: float

    # ── Internal local paths (injected by service) ────────────────────────────
    _local_dataset_path: str
    _charts_dir: str
