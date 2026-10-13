"""Tests for the LLM fallback, chart linking, report grounding, PDF charts and session status."""
import re
import time
from unittest.mock import patch

import pytest
from langchain_core.messages import HumanMessage

import app.agents.llm_client as llm_client
from app.agents.reporter import _charts_text, _verified_stats_text
from app.agents.utils import normalise_finding
from app.agents.visualizer import _link_charts_to_findings
from app.services.analysis_service import _any_analysis_step_succeeded
from app.services.report_service import generate_pdf


# ── Gemini quota circuit breaker ──────────────────────────────────────────────

def test_daily_vs_per_minute_quota_errors():
    daily = "429 You exceeded your current quota ... free_tier_requests, limit: 20 Please retry in 15h18m28s."
    minute = "429 You exceeded your current quota ... free_tier_requests, limit: 5 Please retry in 42.6s."
    assert llm_client._is_daily_quota_error(Exception(daily))
    assert not llm_client._is_daily_quota_error(Exception(minute))
    assert not llm_client._is_daily_quota_error(Exception("503 high demand"))


def test_breaker_blocks_reused_client_per_model():
    llm_client._gemini_disabled_until["gemini-test"] = time.time() + 60
    try:
        client = llm_client._QuotaAwareGemini(model="gemini-test", google_api_key="x")
        with pytest.raises(llm_client.GeminiQuotaExhausted):
            client._generate([HumanMessage("hi")])
        assert llm_client._gemini_available("gemini-other")
    finally:
        llm_client._gemini_disabled_until.pop("gemini-test", None)


def test_fallback_order_main_then_lite_then_groq():
    from app.config import settings
    with patch.object(settings, "gemini_api_key", "x"), patch.object(settings, "groq_api_key", "y"):
        chain = llm_client._make_llm()
        models = [chain.runnable.model] + [getattr(f, "model", None) or f.model_name for f in chain.fallbacks]
        assert [m.removeprefix("models/") for m in models] == [
            settings.default_model, settings.gemini_light_model, settings.groq_model]

        # main model out of quota -> chain starts at lite
        llm_client._gemini_disabled_until[settings.default_model] = time.time() + 60
        try:
            chain = llm_client._make_llm()
            assert chain.runnable.model.removeprefix("models/") == settings.gemini_light_model
        finally:
            llm_client._gemini_disabled_until.pop(settings.default_model, None)


def test_groq_budget_shrinks_once_on_413():
    calls = []

    def fake_generate(self, messages, stop=None, run_manager=None, **kwargs):
        calls.append(kwargs["max_tokens"])
        if len(calls) == 1:
            raise Exception("Error code: 413 ... Limit 8000, Requested 8992, please reduce")
        return "ok"

    with patch("langchain_groq.ChatGroq._generate", fake_generate):
        groq = llm_client._BudgetedGroq(model_name="x", groq_api_key="x")
        assert groq._generate([HumanMessage("a" * 9000)]) == "ok"
    assert len(calls) == 2 and calls[1] == calls[0] - 992 - 100


# ── Visualizer: chart findings get real MinIO paths ───────────────────────────

def test_link_charts_to_findings():
    findings = [
        normalise_finding({"type": "visualization", "title": "A", "visualization_path": "V002"}, "visualizer", 1),
        normalise_finding({"type": "visualization", "title": "B", "visualization_path": "?"}, "visualizer", 2),
    ]
    uploaded = ["charts/s/V001.png", "charts/s/V002.png", "charts/s/V003.png"]
    out = _link_charts_to_findings(findings, uploaded)
    paths = {f["title"]: f["visualization_path"] for f in out}
    assert paths["A"] == "charts/s/V002.png"          # matched by id
    assert paths["B"] == "charts/s/V001.png"          # leftover assigned in order
    assert paths["Chart V003"] == "charts/s/V003.png"  # unmatched chart still gets a finding


# ── Reporter grounding ────────────────────────────────────────────────────────

def test_verified_stats_and_chart_list():
    profile = {"rows": 2, "columns": 1, "columns_meta": [
        {"name": "units", "col_type": "numeric", "null_count": 0, "unique_count": 2,
         "mean": 75.0, "std": 80.6, "min": 18.0, "p50": 75.0, "max": 132.0}]}
    text = _verified_stats_text(profile)
    assert "min 18.0" in text and "max 132.0" in text and "Completeness: 100.0%" in text
    viz = normalise_finding({"type": "visualization", "title": "T"}, "visualizer", 1)
    viz["visualization_path"] = "charts/s/V001.png"
    assert "V001.png: T" in _charts_text([viz])
    assert "No charts" in _charts_text([])


# ── PDF: every stored chart appears exactly once ──────────────────────────────

def _png_bytes(slope: int) -> bytes:
    import io
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    fig, ax = plt.subplots(figsize=(2, 2))
    ax.plot([0, 1], [0, slope])  # distinct images: ReportLab de-duplicates identical ones
    buf = io.BytesIO()
    fig.savefig(buf, format="png")
    plt.close(fig)
    return buf.getvalue()


def test_pdf_embeds_referenced_and_unreferenced_charts():
    paths = ["charts/s/V001.png", "charts/s/V002.png", "charts/s/V003.png"]
    pngs = {p: _png_bytes(i + 1) for i, p in enumerate(paths)}
    with patch("app.services.report_service._fetch_chart_bytes", side_effect=pngs.get):
        md = "# Report\n\n- ![Sales](V001.png) inside a bullet\n\nText."
        pdf = generate_pdf(md, chart_paths=paths, chart_titles={p: "T" for p in paths})
    assert pdf[:5] == b"%PDF-"
    assert _count_pdf_images(pdf) == 3  # V001 inline (from a bullet), V002/V003 appended, none duplicated


def _count_pdf_images(pdf: bytes) -> int:
    """Image XObjects that are not alpha masks (ReportLab may share one mask between images)."""
    image_objs = set(re.findall(rb"(\d+) 0 obj\s*<<[^>]*?/Subtype\s*/Image", pdf))
    mask_objs = set(re.findall(rb"/SMask\s+(\d+) 0 R", pdf))
    return len(image_objs - mask_objs)


# ── Code executor: charts always land in the session folder ──────────────────

def test_executor_ignores_redefined_save_chart(tmp_path):
    from app.agents.tools.code_executor import execute_python
    csv = tmp_path / "d.csv"
    csv.write_text("a,b\n1,2\n3,4\n")
    charts = tmp_path / "charts"
    code = (
        "import matplotlib.pyplot as plt\n"
        "def save_chart(fig, chart_id):\n"          # what the lite model generated
        "    path = f'output/charts/{chart_id}.png'\n"
        "    fig.savefig(path)\n"
        "fig, ax = plt.subplots()\n"
        "ax.plot(df['a'], df['b'])\n"
        "save_chart(fig, 'V001')\n"
    )
    res = execute_python(code, str(csv), "s", str(charts), timeout=120)
    assert res["success"], res["stderr"]
    assert [p.rsplit("\\", 1)[-1].rsplit("/", 1)[-1] for p in res["chart_files"]] == ["V001.png"]


def test_executor_collects_pngs_saved_to_relative_subfolder(tmp_path):
    from app.agents.tools.code_executor import execute_python
    csv = tmp_path / "d.csv"
    csv.write_text("a,b\n1,2\n")
    charts = tmp_path / "charts"
    code = (
        "import os, matplotlib.pyplot as plt\n"
        "os.makedirs('output/charts', exist_ok=True)\n"
        "fig, ax = plt.subplots(); ax.plot([1, 2])\n"
        "fig.savefig('output/charts/extra.png')\n"
    )
    res = execute_python(code, str(csv), "s", str(charts), timeout=120)
    assert res["success"], res["stderr"]
    assert any(p.endswith("extra.png") for p in res["chart_files"])
    assert str(charts) in res["chart_files"][0]  # written under the session folder, not the cwd


# ── Session status ────────────────────────────────────────────────────────────

def test_session_fails_when_no_analysis_step_succeeds():
    plan_only = [{"agent_name": "orchestrator", "status": "completed"},
                 {"agent_name": "profiler", "status": "failed"},
                 {"agent_name": "reporter", "status": "completed"}]
    assert not _any_analysis_step_succeeded(plan_only)
    assert _any_analysis_step_succeeded(plan_only + [{"agent_name": "eda", "status": "completed"}])
