
import sys
import os
import time
import json
import traceback
import pandas as pd

# Add current directory to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from app.config import settings
from app.agents.state import AnalysisState
from app.agents.orchestrator import orchestrator_node
from app.agents.profiler import profiler_node
from app.agents.eda import eda_node
from app.agents.statistician import statistician_node
from app.agents.visualizer import visualizer_node
from app.agents.reporter import reporter_node
from app.agents.graph import analysis_graph

def run_agent_test():
    print("=" * 80)
    print("STARTING FULL AGENTS & PIPELINE TEST Across All Phases")
    print(f"Model configured: {settings.default_model}")
    print(f"LLM Provider: {settings.default_llm_provider}")
    print("=" * 80)

    # Prepare sample dataset path
    dataset_path = os.path.abspath("../test_e2e_phase_check.csv")
    if not os.path.exists(dataset_path):
        dataset_path = os.path.abspath("../test_sample.csv")
    
    print(f"Using test dataset: {dataset_path}")
    df = pd.read_csv(dataset_path)

    # Build initial state
    session_id = f"test_session_{int(time.time())}"
    charts_dir = os.path.join(os.getcwd(), "test_charts", session_id)
    os.makedirs(charts_dir, exist_ok=True)

    numeric_cols = df.select_dtypes(include=["number"]).columns.tolist()
    text_cols = df.select_dtypes(include=["object", "string", "category"]).columns.tolist()
    datetime_cols = df.select_dtypes(include=["datetime", "datetime64"]).columns.tolist()

    columns_meta = []
    for col in df.columns:
        columns_meta.append({
            "name": col,
            "dtype": str(df[col].dtype),
            "null_count": int(df[col].isnull().sum()),
            "distinct_count": int(df[col].nunique()),
        })

    profile = {
        "rows": len(df),
        "columns": len(df.columns),
        "column_names": list(df.columns),
        "columns_meta": columns_meta,
        "sample_rows": df.head(5).to_dict(orient="records"),
        "numeric_cols": numeric_cols,
        "text_cols": text_cols,
        "datetime_cols": datetime_cols,
        "has_nulls": bool(df.isnull().any().any()),
        "memory_mb": round(df.memory_usage(deep=True).sum() / (1024 * 1024), 3),
    }

    state: AnalysisState = {
        "session_id": session_id,
        "dataset_filename": os.path.basename(dataset_path),
        "dataset_profile": profile,
        "user_query": "Identify top sales patterns, perform statistical hypothesis tests on sales across regions, and generate visual charts and executive report.",
        "analysis_plan": {},
        "current_agent": "orchestrator",
        "findings": [],
        "chart_paths": [],
        "report_markdown": "",
        "error_count": 0,
        "step_records": [],
        "_local_dataset_path": dataset_path,
        "_charts_dir": charts_dir,
    }

    test_results = {}
    phase_status = {}

    # ------------------------------------------------------------------
    # Phase 1: Orchestrator Node Test
    # ------------------------------------------------------------------
    print("\n[Phase 1] Testing Orchestrator Agent...")
    try:
        t0 = time.time()
        state = orchestrator_node(state)
        t1 = time.time()
        plan = state.get("analysis_plan", {})
        latest_step = state["step_records"][-1] if state.get("step_records") else {}
        if latest_step.get("status") == "completed" and plan:
            print(f"  [OK] Orchestrator SUCCESS ({t1-t0:.2f}s)")
            print(f"    Summary: {plan.get('analysis_plan', {}).get('summary', 'Plan created')}")
            phase_status["Orchestrator"] = "SUCCESS"
        else:
            print(f"  [FAIL] Orchestrator FAILED or Fallback used: {latest_step.get('error_message')}")
            phase_status["Orchestrator"] = f"FAILED: {latest_step.get('error_message')}"
    except Exception as e:
        print(f"  [FAIL] Orchestrator Exception: {e}")
        traceback.print_exc()
        phase_status["Orchestrator"] = f"EXCEPTION: {str(e)}"

    # ------------------------------------------------------------------
    # Phase 2: Profiler Node Test
    # ------------------------------------------------------------------
    print("\n[Phase 2] Testing Profiler Agent...")
    try:
        t0 = time.time()
        state = profiler_node(state)
        t1 = time.time()
        latest_step = state["step_records"][-1]
        profiler_findings = [f for f in state.get("findings", []) if f.get("agent_name") == "profiler"]
        if latest_step.get("status") == "completed":
            print(f"  [OK] Profiler SUCCESS ({t1-t0:.2f}s) — Found {len(profiler_findings)} profiling insights")
            phase_status["Profiler"] = "SUCCESS"
        else:
            print(f"  [FAIL] Profiler FAILED: {latest_step.get('error_message')}")
            phase_status["Profiler"] = f"FAILED: {latest_step.get('error_message')}"
    except Exception as e:
        print(f"  [FAIL] Profiler Exception: {e}")
        traceback.print_exc()
        phase_status["Profiler"] = f"EXCEPTION: {str(e)}"

    # ------------------------------------------------------------------
    # Phase 3: EDA Node Test
    # ------------------------------------------------------------------
    print("\n[Phase 3] Testing EDA Agent...")
    try:
        t0 = time.time()
        state = eda_node(state)
        t1 = time.time()
        latest_step = state["step_records"][-1]
        eda_findings = [f for f in state.get("findings", []) if f.get("agent_name") == "eda"]
        if latest_step.get("status") == "completed":
            print(f"  [OK] EDA SUCCESS ({t1-t0:.2f}s) — Found {len(eda_findings)} EDA insights")
            phase_status["EDA"] = "SUCCESS"
        else:
            print(f"  [FAIL] EDA FAILED: {latest_step.get('error_message')}")
            phase_status["EDA"] = f"FAILED: {latest_step.get('error_message')}"
    except Exception as e:
        print(f"  [FAIL] EDA Exception: {e}")
        traceback.print_exc()
        phase_status["EDA"] = f"EXCEPTION: {str(e)}"

    # ------------------------------------------------------------------
    # Phase 4: Statistician Node Test
    # ------------------------------------------------------------------
    print("\n[Phase 4] Testing Statistician Agent...")
    try:
        t0 = time.time()
        state = statistician_node(state)
        t1 = time.time()
        latest_step = state["step_records"][-1]
        stats_findings = [f for f in state.get("findings", []) if f.get("agent_name") == "statistician"]
        if latest_step.get("status") in ("completed", "skipped"):
            print(f"  [OK] Statistician {latest_step.get('status').upper()} ({t1-t0:.2f}s) — Generated {len(stats_findings)} statistical test results")
            phase_status["Statistician"] = "SUCCESS"
        else:
            print(f"  [FAIL] Statistician FAILED: {latest_step.get('error_message')}")
            phase_status["Statistician"] = f"FAILED: {latest_step.get('error_message')}"
    except Exception as e:
        print(f"  [FAIL] Statistician Exception: {e}")
        traceback.print_exc()
        phase_status["Statistician"] = f"EXCEPTION: {str(e)}"

    # ------------------------------------------------------------------
    # Phase 5: Visualizer Node Test
    # ------------------------------------------------------------------
    print("\n[Phase 5] Testing Visualizer Agent...")
    try:
        t0 = time.time()
        state = visualizer_node(state)
        t1 = time.time()
        latest_step = state["step_records"][-1]
        chart_paths = state.get("chart_paths", [])
        if latest_step.get("status") == "completed":
            print(f"  [OK] Visualizer SUCCESS ({t1-t0:.2f}s) — Created {len(chart_paths)} charts")
            phase_status["Visualizer"] = "SUCCESS"
        else:
            print(f"  [FAIL] Visualizer FAILED: {latest_step.get('error_message')}")
            phase_status["Visualizer"] = f"FAILED: {latest_step.get('error_message')}"
    except Exception as e:
        print(f"  [FAIL] Visualizer Exception: {e}")
        traceback.print_exc()
        phase_status["Visualizer"] = f"EXCEPTION: {str(e)}"

    # ------------------------------------------------------------------
    # Phase 6: Reporter Node Test
    # ------------------------------------------------------------------
    print("\n[Phase 6] Testing Reporter Agent...")
    try:
        t0 = time.time()
        state = reporter_node(state)
        t1 = time.time()
        latest_step = state["step_records"][-1]
        report_md = state.get("report_markdown", "")
        if latest_step.get("status") == "completed" and len(report_md) > 200:
            print(f"  [OK] Reporter SUCCESS ({t1-t0:.2f}s) — Generated {len(report_md)} char Markdown report")
            phase_status["Reporter"] = "SUCCESS"
        else:
            print(f"  [FAIL] Reporter FAILED/Fallback: {latest_step.get('error_message')}")
            phase_status["Reporter"] = f"FAILED: {latest_step.get('error_message')}"
    except Exception as e:
        print(f"  [FAIL] Reporter Exception: {e}")
        traceback.print_exc()
        phase_status["Reporter"] = f"EXCEPTION: {str(e)}"

    # ------------------------------------------------------------------
    # Summary Report
    # ------------------------------------------------------------------
    print("\n" + "=" * 80)
    print("SUMMARY OF AGENT & PHASE COMPONENT TESTING")
    print("=" * 80)
    all_ok = True
    for agent, status in phase_status.items():
        symbol = "[OK]" if "SUCCESS" in status else "[FAIL]"
        print(f"{symbol} Agent '{agent}': {status}")
        if "SUCCESS" not in status:
            all_ok = False

    print("\nTotal Step Records Executed:", len(state.get("step_records", [])))
    print("Total Findings Collected:", len(state.get("findings", [])))
    print("Total Charts Generated:", len(state.get("chart_paths", [])))
    print("Report Markdown Length:", len(state.get("report_markdown", "")))

    if all_ok:
        print("\nALL AGENTS AND PIPELINE PHASES ARE WORKING PERFECTLY!")
    else:
        print("\nSOME AGENTS ENCOUNTERED ISSUES — SEE LOGS ABOVE.")

    return all_ok

if __name__ == "__main__":
    run_agent_test()
