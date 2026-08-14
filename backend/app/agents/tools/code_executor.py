"""
Safe Python code executor — runs AI-generated code in a subprocess
with a hard timeout. Captures stdout/stderr and any chart files written
to a temp directory.
"""

import os
import sys
import json
import time
import tempfile
import subprocess
import textwrap
from pathlib import Path


# ── Dataset loader injected at top of every generated script ─────────────────
_PREAMBLE_TEMPLATE = """
import os, sys, json, warnings
import pandas as pd
import numpy as np
import matplotlib
matplotlib.use('Agg')   # non-interactive backend — MUST come before pyplot import
import matplotlib.pyplot as plt
import seaborn as sns
try:
    import scipy.stats
except ImportError:
    pass
try:
    import statsmodels.api
    import statsmodels.formula.api
except ImportError:
    pass
warnings.filterwarnings('ignore')

# ── Load dataset ──────────────────────────────────────────────────────────────
_DATASET_PATH = {dataset_path!r}
_CHARTS_DIR   = {charts_dir!r}
_SESSION_ID   = {session_id!r}

def _load_df():
    ext = os.path.splitext(_DATASET_PATH)[1].lower()
    if ext == '.csv':
        return pd.read_csv(_DATASET_PATH, low_memory=False)
    elif ext in ('.xlsx', '.xls'):
        return pd.read_excel(_DATASET_PATH, engine='openpyxl')
    elif ext == '.json':
        return pd.read_json(_DATASET_PATH)
    elif ext == '.parquet':
        return pd.read_parquet(_DATASET_PATH)
    raise ValueError(f"Unsupported: {{ext}}")

df = _load_df()

def save_chart(fig, chart_id: str) -> str:
    \"\"\"Save a matplotlib figure and return the file path.\"\"\"
    path = os.path.join(_CHARTS_DIR, f"{{chart_id}}.png")
    fig.savefig(path, dpi=150, bbox_inches='tight', facecolor='#0f1117')
    plt.close(fig)
    return path

def save_plotly(fig, chart_id: str) -> str:
    \"\"\"Save a plotly figure as PNG and return the file path.\"\"\"
    import plotly.io as pio
    path = os.path.join(_CHARTS_DIR, f"{{chart_id}}.png")
    try:
        pio.write_image(fig, path, width=1200, height=700)
    except Exception:
        # Fallback: save as JSON for browser rendering
        path = path.replace('.png', '.json')
        with open(path, 'w') as f:
            f.write(fig.to_json())
    return path

print(f"[OK] Dataset loaded: {{df.shape[0]}} rows x {{df.shape[1]}} cols")

# ── User code starts below ─────────────────────────────────────────────────────
"""


def execute_python(
    code: str,
    dataset_local_path: str,
    session_id: str,
    charts_dir: str,
    timeout: int = 120,
) -> dict:
    """
    Execute AI-generated Python code safely in a subprocess.

    Returns:
        {
            "success": bool,
            "stdout": str,
            "stderr": str,
            "duration_seconds": float,
            "chart_files": list[str],   # absolute paths of any PNG files written
        }
    """
    os.makedirs(charts_dir, exist_ok=True)

    # Build the full script with preamble
    preamble = textwrap.dedent(_PREAMBLE_TEMPLATE.format(
        dataset_path=dataset_local_path,
        charts_dir=charts_dir,
        session_id=session_id,
    ))
    full_script = preamble + "\n" + code

    # Write to a temp file
    with tempfile.NamedTemporaryFile(
        mode="w", suffix=".py", delete=False, encoding="utf-8"
    ) as f:
        f.write(full_script)
        script_path = f.name

    start = time.time()
    try:
        result = subprocess.run(
            [sys.executable, script_path],
            capture_output=True,
            text=True,
            timeout=timeout,
            env={**os.environ, "PYTHONDONTWRITEBYTECODE": "1"},
        )
        duration = time.time() - start

        # Collect any chart files written during execution
        chart_files = []
        if os.path.isdir(charts_dir):
            chart_files = [
                str(Path(charts_dir) / f)
                for f in os.listdir(charts_dir)
                if f.endswith((".png", ".json"))
            ]

        return {
            "success": result.returncode == 0,
            "stdout": result.stdout[:8000],   # cap at 8KB
            "stderr": result.stderr[:4000] if result.returncode != 0 else "",
            "duration_seconds": round(duration, 2),
            "chart_files": chart_files,
        }

    except subprocess.TimeoutExpired:
        return {
            "success": False,
            "stdout": "",
            "stderr": f"Code execution timed out after {timeout} seconds.",
            "duration_seconds": timeout,
            "chart_files": [],
        }
    except Exception as e:
        return {
            "success": False,
            "stdout": "",
            "stderr": str(e),
            "duration_seconds": time.time() - start,
            "chart_files": [],
        }
    finally:
        try:
            os.unlink(script_path)
        except OSError:
            pass
