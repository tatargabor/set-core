"""Test: verdict.json with findings loads cleanly; legacy files still parse.

See OpenSpec change: fix-e2e-infra-systematic (T2.1.6).

The new `findings: [...]` field on `GateVerdict` is forward-compatible:
  * New writers emit it when extractors produce findings.
  * Old sidecars (no findings key) still load into GateVerdict successfully.
  * retry_context rendering prefers findings when present; falls back to
    summary otherwise.
"""

from __future__ import annotations

import json
import sys
from dataclasses import asdict
from pathlib import Path

_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(_ROOT / "lib"))


def test_legacy_sidecar_without_findings_loads_cleanly(tmp_path: Path):
    from set_orch.gate_verdict import GateVerdict, read_verdict_sidecar

    legacy = {
        "gate": "review",
        "verdict": "fail",
        "critical_count": 2,
        "high_count": 0,
        "medium_count": 0,
        "low_count": 0,
        "source": "classifier_confirmed",
        "change": "add-cart",
        "summary": "2 critical findings",
        # No "findings" key — old file format.
    }
    session_path = tmp_path / "session.jsonl"
    session_path.write_text("{}")
    sidecar_path = tmp_path / "session.verdict.json"
    sidecar_path.write_text(json.dumps(legacy))

    result = read_verdict_sidecar(session_path)
    assert result is not None
    assert result.verdict == "fail"
    assert result.findings == []  # default-filled, never None


def test_new_sidecar_with_findings_round_trips(tmp_path: Path):
    from set_orch.findings import Finding, fingerprint
    from set_orch.gate_verdict import (
        GateVerdict, read_verdict_sidecar, write_verdict_sidecar,
    )

    session_path = tmp_path / "session.jsonl"
    session_path.write_text("{}")

    f1 = Finding(id="1", severity="critical", title="SQLi",
                 file="src/a.ts", line_start=10,
                 fingerprint=fingerprint("src/a.ts", 10, "SQLi"))
    f2 = Finding(id="2", severity="warning", title="loose type",
                 file="src/b.ts", line_start=20,
                 fingerprint=fingerprint("src/b.ts", 20, "loose type"))
    verdict = GateVerdict(
        gate="review", verdict="fail", critical_count=1,
        summary="see findings", findings=[asdict(f1), asdict(f2)],
    )
    write_verdict_sidecar(session_path, verdict)

    loaded = read_verdict_sidecar(session_path)
    assert loaded is not None
    assert len(loaded.findings) == 2
    assert loaded.findings[0]["title"] == "SQLi"
    assert loaded.findings[0]["fingerprint"] == f1.fingerprint


def test_retry_context_prefers_findings_when_present(tmp_path: Path):
    """Smoke test: the retry-context builder renders a findings block when
    change.extras.findings is populated."""
    from set_orch.engine import _build_reset_retry_context

    class _FakeChange:
        name = "add-cart"
        extras = {
            "findings": [
                {"id": "1", "severity": "critical", "title": "SQLi in getProduct",
                 "file": "src/a.ts", "line_start": 42,
                 "fix_block": "parameterize via prisma.findUnique",
                 "fingerprint": "abc12345", "confidence": "high"},
            ],
            "review_output": "full log here",
        }
        e2e_result = None
        failure_reason = ""

    ctx = _build_reset_retry_context(_FakeChange(), str(tmp_path))
    assert "Structured findings" in ctx, ctx
    assert "SQLi in getProduct" in ctx
    assert "src/a.ts" in ctx
    assert "abc12345" in ctx


def test_retry_context_falls_back_to_summary_when_no_findings(tmp_path: Path):
    """No findings → no Structured findings block (but still renders
    review_output section)."""
    from set_orch.engine import _build_reset_retry_context

    class _FakeChange:
        name = "add-cart"
        extras = {"review_output": "[CRITICAL] fallback summary block"}
        e2e_result = None
        failure_reason = ""

    ctx = _build_reset_retry_context(_FakeChange(), str(tmp_path))
    assert "Structured findings" not in ctx, "findings block must be absent"
    assert "fallback summary block" in ctx, "summary path must still render"
