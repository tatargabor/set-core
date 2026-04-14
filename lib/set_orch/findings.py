"""Structured gate findings extraction.

See OpenSpec change: fix-e2e-infra-systematic, Tier 2, T2.1.

`Finding` is the atomic unit of a structured gate verdict. A gate that fails
can emit zero or more Findings; each carries FILE / LINE / FIX in a form the
retry_context builder can render verbatim (instead of relying on the 1-line
`summary` that historically lost the reviewer's concrete fix instructions).

Each extractor:
  * accepts the captured gate output (stdout + stderr concatenated)
  * returns `list[Finding]`; `[]` when nothing matched, `[]` on parse errors
  * NEVER raises — extractor failures degrade to summary-only retry_context

Fingerprints give retries a stable identity per (file, line, title-prefix) so
Tier 3 convergence detection can count recurring findings across iterations.
"""

from __future__ import annotations

import hashlib
import logging
import re
from dataclasses import asdict, dataclass, field
from typing import Any

logger = logging.getLogger(__name__)


@dataclass
class Finding:
    """One structured gate finding.

    Stable fields across extractors — optional ones are empty strings or None
    when the source doesn't provide them. This dataclass is JSON-serializable
    via `asdict(finding)`.
    """

    id: str = ""                 # extractor-assigned id (e.g. "review-1", "e2e-3")
    severity: str = "warning"    # "critical" | "warning" | "info"
    title: str = ""              # one-line headline
    file: str = ""               # relative path, best-effort
    line_start: int = 0
    line_end: int = 0
    code_context: str = ""       # few-line snippet near the offending site
    fix_block: str = ""          # the FIX instructions the gate emitted
    fingerprint: str = ""        # stable hash (file:line:title[:50])
    confidence: str = "high"     # "high" | "medium" | "low"

    def to_dict(self) -> dict:
        return asdict(self)


def fingerprint(file: str, line_start: int, title: str) -> str:
    """Return a stable 8-char hex fingerprint for a finding.

    Same finding across retries (same FILE:LINE:TITLE prefix) yields the same
    fingerprint — Tier 3 uses these to detect convergence failures.
    """
    key = f"{file}:{line_start}:{title[:50]}"
    return hashlib.sha256(key.encode("utf-8", errors="replace")).hexdigest()[:8]


def _set_fingerprint(f: Finding) -> Finding:
    f.fingerprint = fingerprint(f.file, f.line_start, f.title)
    return f


# ─── Extractors ──────────────────────────────────────────────────────
#
# Each extractor parses the raw output a gate captured into a normalized
# list of Finding objects. They are intentionally permissive — missing
# fields stay empty, unparseable regions become zero findings, and nothing
# raises. The caller (gate_verdict.persist_gate_verdict) attaches the result
# to the verdict sidecar when non-empty; absence is backward-compatible.


_REVIEW_CRITICAL_RE = re.compile(
    r"^\s*(?:\*\*)?\[CRITICAL\](?:\*\*)?\s*(?:-\s*)?(?P<title>.+?)\s*$",
    re.MULTILINE,
)
_REVIEW_FILE_RE = re.compile(
    r"(?:^|\n)\s*(?:File|file|Location|Path)\s*:\s*(?P<file>\S+?)"
    r"(?::(?P<line>\d+))?\s*(?:\n|$)"
)
_REVIEW_FIX_RE = re.compile(
    r"(?:^|\n)(?:\*\*)?(?:Fix|FIX|Proposed fix)(?:\*\*)?\s*:\s*"
    r"(?P<fix>.+?)(?=\n\s*(?:\*\*)?(?:\[|File\s*:|Location\s*:|---|$))",
    re.DOTALL,
)


def extract_review_findings(output: str) -> list[Finding]:
    """Parse a reviewer's output into structured findings.

    Targets the common reviewer format:

        [CRITICAL] <short title>
        File: path/to/file.ts:123
        Fix: <multi-line instructions>

    Falls back to one Finding per `[CRITICAL]` block when FILE/FIX cannot be
    located. Returns `[]` on any parse error.
    """
    if not output:
        return []
    try:
        findings: list[Finding] = []
        chunks = _split_by_marker(output, "[CRITICAL]")
        for idx, chunk in enumerate(chunks, start=1):
            title_m = re.search(r"\[CRITICAL\]\s*(?:-\s*)?(.+)", chunk)
            title = (title_m.group(1).strip() if title_m else "").splitlines()[0:1]
            title_str = title[0] if title else ""

            file_m = _REVIEW_FILE_RE.search(chunk)
            file_str = file_m.group("file").strip() if file_m else ""
            line_start = int(file_m.group("line") or 0) if file_m and file_m.group("line") else 0

            fix_m = _REVIEW_FIX_RE.search(chunk)
            fix_str = fix_m.group("fix").strip() if fix_m else ""

            f = Finding(
                id=f"review-{idx}",
                severity="critical",
                title=title_str,
                file=file_str,
                line_start=line_start,
                line_end=line_start,
                fix_block=fix_str,
                confidence="high" if file_str else "medium",
            )
            findings.append(_set_fingerprint(f))
        return findings
    except Exception:
        logger.warning("extract_review_findings failed — falling back to summary", exc_info=True)
        return []


def _split_by_marker(text: str, marker: str) -> list[str]:
    """Split text into chunks that each start with `marker`."""
    if marker not in text:
        return []
    parts = text.split(marker)
    # parts[0] is prelude before first marker — skip.
    return [marker + p for p in parts[1:]]


# Spec-verify format is similar enough to review that we share the regexes
# but tag the id prefix differently + accept `[FAIL]` tags too.
_SPEC_VERIFY_MARKERS = ("[CRITICAL]", "[FAIL]", "[MISSING]")


def extract_spec_verify_findings(output: str) -> list[Finding]:
    """Parse `spec_verify` output into structured findings.

    Accepts `[CRITICAL]`, `[FAIL]`, `[MISSING]` markers — spec_verify uses
    them inconsistently across iterations, so we accept all three.
    """
    if not output:
        return []
    try:
        findings: list[Finding] = []
        idx = 0
        for marker in _SPEC_VERIFY_MARKERS:
            for chunk in _split_by_marker(output, marker):
                idx += 1
                title_m = re.search(rf"{re.escape(marker)}\s*(?:-\s*)?(.+)", chunk)
                title = ""
                if title_m:
                    lines = title_m.group(1).strip().splitlines()
                    title = lines[0] if lines else ""

                file_m = _REVIEW_FILE_RE.search(chunk)
                file_str = file_m.group("file").strip() if file_m else ""
                line_start = int(file_m.group("line") or 0) if file_m and file_m.group("line") else 0

                fix_m = _REVIEW_FIX_RE.search(chunk)
                fix_str = fix_m.group("fix").strip() if fix_m else ""

                severity = "critical" if marker == "[CRITICAL]" else "warning"
                f = Finding(
                    id=f"spec-verify-{idx}",
                    severity=severity,
                    title=title,
                    file=file_str,
                    line_start=line_start,
                    line_end=line_start,
                    fix_block=fix_str,
                    confidence="high" if file_str else "medium",
                )
                findings.append(_set_fingerprint(f))
        return findings
    except Exception:
        logger.warning("extract_spec_verify_findings failed — falling back to summary", exc_info=True)
        return []


# Playwright numbered failure blocks:
#   1) [chromium] › tests/e2e/cart.spec.ts:42 › REQ-CART-001 adds item to cart
#      Error: expect(received).toEqual(expected)
_E2E_FAIL_HEADER_RE = re.compile(
    r"^\s*(?P<idx>\d+)\)\s+\[(?P<project>[^\]]+)\]\s+[›»]\s+"
    r"(?P<file>[^\s:]+\.spec\.\w+):(?P<line>\d+)\s+[›»]\s+(?P<title>.+?)\s*$",
    re.MULTILINE,
)
_ANSI_RE = re.compile(r"\x1b\[[0-9;?]*[A-Za-z]")


def extract_e2e_findings(output: str) -> list[Finding]:
    """Parse Playwright output into structured findings, one per failing test.

    The header line yields file/line/title deterministically; the body (error
    message + stack) is captured up to the next failure header or EOF. Strips
    ANSI escape sequences first so headers match even on terminal-style output.
    """
    if not output:
        return []
    try:
        clean = _ANSI_RE.sub("", output)
        headers = list(_E2E_FAIL_HEADER_RE.finditer(clean))
        findings: list[Finding] = []
        for i, m in enumerate(headers):
            body_start = m.end()
            body_end = headers[i + 1].start() if i + 1 < len(headers) else len(clean)
            body = clean[body_start:body_end].strip()
            title = m.group("title").strip()
            file_ = m.group("file").strip()
            line_start = int(m.group("line"))
            # Pluck the first "Error: ..." line if present as a concise fix hint.
            err_line = ""
            em = re.search(r"^\s*(Error:\s*.+?)\s*$", body, re.MULTILINE)
            if em:
                err_line = em.group(1)
            f = Finding(
                id=f"e2e-{m.group('idx')}",
                severity="critical",
                title=title,
                file=file_,
                line_start=line_start,
                line_end=line_start,
                code_context=body[:1500],
                fix_block=err_line,
                confidence="high",
            )
            findings.append(_set_fingerprint(f))
        return findings
    except Exception:
        logger.warning("extract_e2e_findings failed — falling back to summary", exc_info=True)
        return []


def render_findings_block(findings: list[Finding], *, limit: int = 20) -> str:
    """Render findings as a human-readable block for the retry_context.

    Up to `limit` findings, ordered: critical → warning → info; then original
    order within each group. The block is Markdown-friendly and deterministic.
    """
    if not findings:
        return ""
    ordered: list[Finding] = []
    for sev in ("critical", "warning", "info"):
        ordered.extend([f for f in findings if f.severity == sev])
    ordered.extend([f for f in findings if f.severity not in ("critical", "warning", "info")])

    lines: list[str] = [f"### Structured findings ({len(findings)} total)", ""]
    for f in ordered[:limit]:
        loc = f.file + (f":" + str(f.line_start) if f.line_start > 0 else "")
        sev_tag = f"[{f.severity.upper()}]"
        lines.append(f"- **{sev_tag}** {f.title} _(fp: {f.fingerprint})_")
        if loc:
            lines.append(f"  - Location: `{loc}`")
        if f.fix_block:
            first_fix_line = f.fix_block.splitlines()[0][:200]
            lines.append(f"  - Fix: {first_fix_line}")
    if len(findings) > limit:
        lines.append("")
        lines.append(f"_... and {len(findings) - limit} more findings (truncated)_")
    return "\n".join(lines) + "\n"


def findings_from_dicts(raw: list[Any]) -> list[Finding]:
    """Rehydrate Finding objects from a list of dicts (read from verdict JSON).

    Unknown keys are dropped; missing keys fall back to dataclass defaults.
    Returns `[]` on any TypeError.
    """
    if not raw:
        return []
    known = {
        "id", "severity", "title", "file", "line_start", "line_end",
        "code_context", "fix_block", "fingerprint", "confidence",
    }
    out: list[Finding] = []
    for d in raw:
        if not isinstance(d, dict):
            continue
        clean = {k: v for k, v in d.items() if k in known}
        try:
            out.append(Finding(**clean))
        except TypeError:
            continue
    return out
