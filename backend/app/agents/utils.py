"""
Shared utilities used by all agent nodes:
- parse_findings_from_output: extracts FINDINGS_JSON from code executor stdout
- broadcast: sends a WebSocket event via the event queue (injected at runtime)
- make_step_record: creates a consistently-structured AgentStepRecord
"""

import json
import time
import uuid
from typing import Callable, Any
from app.agents.state import AgentStepRecord, FindingRecord


def parse_findings_from_output(stdout: str) -> list[dict]:
    """
    Extract findings list from code executor stdout.
    The agent code is expected to print:
        print("FINDINGS_JSON:" + json.dumps(findings_list))
    """
    findings = []
    for line in stdout.splitlines():
        if line.startswith("FINDINGS_JSON:"):
            try:
                raw = json.loads(line[len("FINDINGS_JSON:"):])
                if isinstance(raw, list):
                    findings = raw
            except json.JSONDecodeError:
                pass
            break
    return findings


def normalise_finding(f: dict, agent_name: str, idx: int) -> FindingRecord:
    """Coerce an arbitrary finding dict into a proper FindingRecord."""
    return FindingRecord(
        finding_id=f.get("finding_id", f"{agent_name[:1].upper()}{idx:03d}"),
        agent_name=agent_name,
        finding_type=f.get("type", "profile"),
        title=f.get("title", "Untitled Finding"),
        description=f.get("description", ""),
        evidence=f.get("evidence", {}),
        confidence=f.get("confidence", "medium"),
        hypothesis=f.get("hypothesis", f.get("suggested_hypothesis", "")),
        visualization_path=f.get("visualization_path", f.get("visualization_hint", "")),
    )


def make_step_record(
    agent_name: str,
    step_index: int,
    status: str,
    message: str,
    code_executed: str = "",
    code_output: str = "",
    error_message: str = "",
    duration_seconds: float = 0.0,
    output_data: dict | None = None,
) -> AgentStepRecord:
    return AgentStepRecord(
        agent_name=agent_name,
        step_index=step_index,
        status=status,
        message=message,
        code_executed=code_executed,
        code_output=code_output,
        error_message=error_message,
        duration_seconds=duration_seconds,
        output_data=output_data or {},
    )


def summarise_findings(findings: list[FindingRecord], max_chars: int = 3000) -> str:
    """Return a compact text summary of findings for use in subsequent prompts."""
    lines = []
    for f in findings:
        lines.append(
            f"[{f['finding_id']}] {f['title']} ({f['confidence']} confidence): {f['description'][:200]}"
        )
    summary = "\n".join(lines)
    return summary[:max_chars]


def extract_code_block(text: str) -> str:
    """
    Strip markdown fences if the LLM wrapped code in ```python ... ```
    even though we asked it not to.
    """
    if "```" in text:
        lines = text.split("\n")
        inside = False
        code_lines = []
        for line in lines:
            if line.strip().startswith("```"):
                inside = not inside
                continue
            if inside:
                code_lines.append(line)
        return "\n".join(code_lines)
    return text


def extract_text_from_response(content: Any) -> str:
    """
    Extract plain text from an LLM response content value.

    Gemini 3.5 Flash (thinking models) return content as a list of blocks:
      [{'type': 'thinking', 'thinking': '...'}, {'type': 'text', 'text': '...'}]

    Older models return content as a plain string.
    This helper handles both formats.
    """
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        # Collect only 'text' type blocks, skip 'thinking' blocks
        parts = []
        for block in content:
            if isinstance(block, dict):
                if block.get("type") == "text":
                    parts.append(block.get("text", ""))
                elif "text" in block:
                    parts.append(block["text"])
            elif isinstance(block, str):
                parts.append(block)
        return "\n".join(parts).strip()
    return str(content)

