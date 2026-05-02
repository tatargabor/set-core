"""Unified LLM verdict classifier for gate output parsing.

Motivation
----------
Multiple gates in set-core (review, spec_verify, investigator diagnosis) run
a primary LLM call and then need to derive a structured verdict (pass/fail +
critical count + findings list) from the LLM's prose output. Historically we
parsed this output with body regex or keyword heuristics — and twice in the
last two weeks a retry review explicitly said "3 NOT_FIXED [CRITICAL]" in a
format the parser did not recognise, silently passing the gate.

The fix is a format-agnostic verdict extractor: a small second LLM pass
(Sonnet) reads the primary output as unstructured text and returns a JSON
object describing the findings. The classifier has no knowledge of the gate
type or the severity rubric — it only extracts what is already in the text.
Callers pass in the schema they want and interpret the result.

Related commit: `701bdbc2 fix: spec-verify CRITICAL_COUNT sentinel` — the
sentinel-only precursor to this module.

Usage
-----
    from set_orch.llm_verdict import classify_verdict, REVIEW_SCHEMA

    result = classify_verdict(
        primary_output=review_text,
        schema=REVIEW_SCHEMA,
        purpose="review",
    )
    if result.critical_count > 0:
        block_merge(result.findings)

Any classifier error (timeout, JSON decode, missing field, network error)
produces a fail-safe ClassifierResult with verdict="fail", critical_count=1,
and error set. Callers decide whether to treat classifier errors as blocking
or pass-through — the review gate treats them as "no new information" (fast
path already said clean), spec-verify treats them as fail-closed (no other
trustworthy signal).
"""

from __future__ import annotations

import json
import logging
import re
from dataclasses import dataclass, field
from typing import Any

logger = logging.getLogger(__name__)


# ─── Result type ─────────────────────────────────────────────────────

@dataclass
class ClassifierResult:
    """Structured verdict returned by classify_verdict().

    Fields:
        verdict: "pass" or "fail" — the top-level decision
        critical_count: number of CRITICAL severity findings
        high_count: number of HIGH severity findings
        medium_count: number of MEDIUM severity findings
        low_count: number of LOW severity findings
        findings: list of {severity, summary, file, line, fix} dicts
        raw_json: the full parsed JSON object from the classifier
        error: None if successful; a short machine-readable error code otherwise
               (timeout, exit_nonzero, json_decode_error, missing_field:<name>,
                empty_output, no_json_object)
        elapsed_ms: wall-clock duration of the classifier call
    """
    verdict: str
    critical_count: int
    high_count: int = 0
    medium_count: int = 0
    low_count: int = 0
    findings: list[dict] = field(default_factory=list)
    raw_json: dict = field(default_factory=dict)
    error: str | None = None
    elapsed_ms: int = 0
    # Severity downgrades: list of {from, to, summary} entries recorded
    # when the classifier lowers a reviewer-tagged severity per the rubric.
    downgrades: list[dict] = field(default_factory=list)


# ─── Schemas ────────────────────────────────────────────────────────

# JSON schemas are expressed as plain dicts so callers can easily
# inspect/modify them and the classifier prompt can embed them via
# json.dumps(). We do not use jsonschema validation — the classifier
# prompt is the contract, and we validate the bare minimum required
# fields in _validate_classifier_json().

REVIEW_SCHEMA: dict = {
    "verdict": "pass|fail",
    "critical_count": "integer count of CRITICAL severity findings",
    "high_count": "integer count of HIGH severity findings",
    "medium_count": "integer count of MEDIUM severity findings",
    "low_count": "integer count of LOW severity findings",
    "findings": [
        {
            "severity": "CRITICAL|HIGH|MEDIUM|LOW",
            "summary": "one-line description",
            "file": "path or empty string",
            "line": "line number or empty string",
            "fix": "suggested fix or empty string",
        },
    ],
    "downgrades": [
        {
            "from": "CRITICAL|HIGH|MEDIUM|LOW — the reviewer's original tag",
            "to": "CRITICAL|HIGH|MEDIUM|LOW — the corrected tag per rubric",
            "summary": "short description of the finding that was downgraded",
        },
    ],
}

SPEC_VERIFY_SCHEMA: dict = {
    "verdict": "pass|fail",
    "critical_count": "integer count of CRITICAL spec-coverage gaps",
    "high_count": "integer count of HIGH spec-coverage gaps",
    "medium_count": "integer count",
    "low_count": "integer count",
    "findings": [
        {
            "severity": "CRITICAL|HIGH|MEDIUM|LOW",
            "summary": "which requirement is not covered",
            "file": "file path if applicable",
            "line": "line number if applicable",
            "fix": "what to add",
        },
    ],
}

INVESTIGATOR_SCHEMA: dict = {
    "verdict": "pass|fail",
    "critical_count": "always 1 if impact=high, else 0",
    "high_count": 0,
    "medium_count": 0,
    "low_count": 0,
    "findings": [],
    "impact": "low|medium|high",
    "fix_scope": "single_file|multi_file|config_override",
    "fix_target": "framework|consumer|both",
    "confidence": "float 0.0-1.0",
    "root_cause": "one paragraph description",
    "suggested_fix": "one paragraph description",
}


REQUIRED_FIELDS = ("verdict", "critical_count")


# ─── Public API ────────────────────────────────────────────────────

def classify_verdict(
    primary_output: str,
    schema: dict,
    *,
    model: str = "",
    purpose: str = "classify",
    timeout: int = 120,
    event_bus: Any = None,
    scope_context: str = "",
) -> ClassifierResult:
    """Run a second LLM pass to classify primary_output into structured JSON.

    Args:
        primary_output: the raw narrative from the primary LLM call (review
            text, verify text, investigator proposal, etc.)
        schema: a dict describing the expected JSON shape. The dict is
            serialized into the classifier prompt so the model knows what
            fields to emit.
        model: classifier model short name. Empty string (default) resolves
            via model_config.resolve_model("classifier") — operator can
            override via orchestration.yaml::models.classifier.
        purpose: short string used for logging and event correlation.
        timeout: seconds before the classifier call is killed.
        event_bus: optional event bus for emitting CLASSIFIER_CALL events.

    Returns:
        ClassifierResult. On any error the result has verdict="fail",
        critical_count=1, and error set to a short code.
    """
    if not model:
        from .model_config import resolve_model
        model = resolve_model("classifier")

    # Import lazily to avoid a circular import: subprocess_utils imports
    # events which may import verifier which imports this module.
    from .subprocess_utils import run_claude_logged

    if not primary_output or not primary_output.strip():
        logger.warning("classify_verdict[%s]: empty primary_output, returning fail-safe", purpose)
        result = _fail_safe("empty_output", 0)
        _emit_classifier_event(event_bus, purpose, 0, result)
        return result

    prompt = _build_classifier_prompt(primary_output, schema, scope_context=scope_context)
    primary_bytes = len(primary_output.encode("utf-8"))

    logger.info(
        "classify_verdict[%s] START (primary=%d bytes, model=%s)",
        purpose, primary_bytes, model,
    )

    try:
        claude_result = run_claude_logged(
            prompt,
            purpose=f"classify_{purpose}",
            model=model,
            timeout=timeout,
        )
    except Exception as exc:
        logger.warning("classify_verdict[%s] exception: %s", purpose, exc)
        result = _fail_safe(f"exception:{type(exc).__name__}", 0)
        _emit_classifier_event(event_bus, purpose, primary_bytes, result)
        return result

    elapsed = getattr(claude_result, "duration_ms", 0) or 0

    if claude_result.exit_code != 0:
        err = "timeout" if claude_result.timed_out else f"exit_{claude_result.exit_code}"
        logger.warning(
            "classify_verdict[%s] FAIL exit=%d timed_out=%s elapsed=%dms",
            purpose, claude_result.exit_code, claude_result.timed_out, elapsed,
        )
        result = _fail_safe(err, elapsed)
        _emit_classifier_event(event_bus, purpose, primary_bytes, result)
        return result

    raw_text = claude_result.stdout or ""
    parsed = _extract_json(raw_text)
    if parsed is None:
        logger.warning(
            "classify_verdict[%s] no JSON object in classifier output (%d chars)",
            purpose, len(raw_text),
        )
        result = _fail_safe("no_json_object", elapsed)
        _emit_classifier_event(event_bus, purpose, primary_bytes, result)
        return result

    missing = _validate_required(parsed)
    if missing:
        logger.warning("classify_verdict[%s] missing required field: %s", purpose, missing)
        result = _fail_safe(f"missing_field:{missing}", elapsed, raw_json=parsed)
        _emit_classifier_event(event_bus, purpose, primary_bytes, result)
        return result

    result = _build_result(parsed, elapsed)
    logger.info(
        "classify_verdict[%s] END verdict=%s critical=%d high=%d medium=%d low=%d elapsed=%dms",
        purpose, result.verdict, result.critical_count, result.high_count,
        result.medium_count, result.low_count, elapsed,
    )
    _emit_classifier_event(event_bus, purpose, primary_bytes, result)
    return result


# ─── Internal helpers ──────────────────────────────────────────────

def _build_classifier_prompt(
    primary_output: str, schema: dict, *, scope_context: str = "",
) -> str:
    """Construct the Sonnet classifier prompt from schema + primary output."""
    schema_json = json.dumps(schema, indent=2)
    scope_rule = ""
    if scope_context:
        scope_rule = (
            "7. SCOPE FILTER: This review was for a single change with scope:\n"
            f"   {scope_context}\n"
            "   Findings about missing functionality OUTSIDE this scope (e.g., "
            "\"missing middleware\" when auth is in a different change, \"no "
            "mutation tests\" when the change has no mutations) are NOT CRITICAL. "
            "Downgrade such out-of-scope findings to LOW or exclude them. "
            "Only count findings about actual bugs/issues in code WITHIN the "
            "diff as CRITICAL.\n"
        )
    return (
        "You are a gate verdict extractor. Your job is to read the output of "
        "another LLM and produce a structured JSON verdict describing its "
        "findings. You extract ONLY findings that are explicitly present in "
        "the output — do not invent, infer, or hallucinate findings that are "
        "not there.\n"
        "\n"
        "Return a JSON object matching this exact shape:\n"
        f"{schema_json}\n"
        "\n"
        "Rules:\n"
        "1. `verdict` is \"pass\" if critical_count == 0, otherwise \"fail\".\n"
        "2. Severity counts (`critical_count`, `high_count`, ...) are the "
        "number of distinct findings at each severity level.\n"
        "3. A finding marked `NOT_FIXED`, `REVIEW BLOCKED`, `FAIL`, "
        "`CRITICAL`, or similar is a CRITICAL finding UNLESS the rubric in "
        "rule 8 says it should be lower.\n"
        "4. A finding marked `FIXED`, `RESOLVED`, `PASS`, or similar is NOT "
        "a finding — do not count it.\n"
        "5. Quoted references to prior findings (`\"previous ISSUE: [CRITICAL]\"`) "
        "are NOT findings — only current findings count.\n"
        "6. Respond with ONLY the JSON object. No preamble, no markdown "
        "fences, no commentary. The response must start with `{` and end "
        "with `}`.\n"
        f"{scope_rule}"
        "8. SEVERITY RUBRIC: Apply this tiering when the reviewer's tag is "
        "ambiguous OR when the reviewer escalated a convention violation to "
        "CRITICAL.\n"
        "   - CRITICAL: crashes the app, exposes secrets, leaks other users' "
        "data, allows privilege escalation, or causes data loss.\n"
        "   - HIGH: produces incorrect output or broken UX in a primary user "
        "path (wrong totals, broken checkout, form shows success on error).\n"
        "   - MEDIUM: violates a project rule or convention without breaking "
        "functionality (raw <button> instead of shadcn Button, hardcoded "
        "color instead of design token, fragile test selectors).\n"
        "   - LOW: code hygiene, outdated comments, missing trailing newlines, "
        "accessibility gaps in secondary views.\n"
        "   When a reviewer-tagged CRITICAL does not meet the CRITICAL bar, "
        "DOWNGRADE it: lower `critical_count` and raise `medium_count` (or "
        "`high_count`) and add an entry to the `downgrades` list with the "
        "shape `{\"from\": \"CRITICAL\", \"to\": \"MEDIUM\", \"summary\": "
        "\"short description\"}`. Default to the LOWER tier in doubt.\n"
        "9. SEVERITY DEFAULT: If a finding lists no explicit severity tag, "
        "apply rule 8's rubric and default to the LOWER of two ambiguous tiers.\n"
        "\n"
        "<<<BEGIN OUTPUT>>>\n"
        f"{primary_output}\n"
        "<<<END OUTPUT>>>\n"
    )


_JSON_FENCE_RE = re.compile(r"```(?:json)?\s*\n?(.*?)\n?```", re.DOTALL)


def _extract_json(text: str) -> dict | None:
    """Extract a JSON object from LLM text output.

    Handles three cases:
    1. Raw JSON: text is already a JSON object → json.loads directly
    2. Fenced JSON: ```json ... ``` → strip fence and parse
    3. JSON with preamble: "Here is the result: { ... }" → brace-match
    """
    if not text:
        return None

    stripped = text.strip()

    # Case 1: raw JSON
    if stripped.startswith("{") and stripped.endswith("}"):
        try:
            parsed = json.loads(stripped)
            return parsed if isinstance(parsed, dict) else None
        except json.JSONDecodeError:
            pass

    # Case 2: fenced
    m = _JSON_FENCE_RE.search(stripped)
    if m:
        try:
            parsed = json.loads(m.group(1).strip())
            return parsed if isinstance(parsed, dict) else None
        except json.JSONDecodeError:
            pass

    # Case 3: brace-match the first balanced { ... } block
    start = stripped.find("{")
    if start == -1:
        return None
    depth = 0
    in_string = False
    escape = False
    for i in range(start, len(stripped)):
        ch = stripped[i]
        if escape:
            escape = False
            continue
        if ch == "\\":
            escape = True
            continue
        if ch == '"' and not escape:
            in_string = not in_string
            continue
        if in_string:
            continue
        if ch == "{":
            depth += 1
        elif ch == "}":
            depth -= 1
            if depth == 0:
                try:
                    parsed = json.loads(stripped[start:i + 1])
                    return parsed if isinstance(parsed, dict) else None
                except json.JSONDecodeError:
                    return None
    return None


def _validate_required(parsed: dict) -> str | None:
    """Return the name of the first missing required field, or None."""
    for name in REQUIRED_FIELDS:
        if name not in parsed:
            return name
    # `critical_count` must be an int-compatible value
    try:
        int(parsed.get("critical_count", 0))
    except (TypeError, ValueError):
        return "critical_count"
    return None


def _build_result(parsed: dict, elapsed_ms: int) -> ClassifierResult:
    """Build a ClassifierResult from a validated parsed JSON dict."""
    verdict = str(parsed.get("verdict", "fail")).lower()
    if verdict not in ("pass", "fail"):
        verdict = "fail"

    # Coerce counts to int safely
    def _count(key: str) -> int:
        try:
            return int(parsed.get(key, 0) or 0)
        except (TypeError, ValueError):
            return 0

    findings_raw = parsed.get("findings") or []
    findings: list[dict] = []
    if isinstance(findings_raw, list):
        for f in findings_raw:
            if isinstance(f, dict):
                findings.append({
                    "severity": str(f.get("severity", "MEDIUM")).upper(),
                    "summary": str(f.get("summary", "")),
                    "file": str(f.get("file", "")),
                    "line": str(f.get("line", "")),
                    "fix": str(f.get("fix", "")),
                })

    downgrades_raw = parsed.get("downgrades") or []
    downgrades: list[dict] = []
    if isinstance(downgrades_raw, list):
        for d in downgrades_raw:
            if isinstance(d, dict):
                downgrades.append({
                    "from": str(d.get("from", "")).upper(),
                    "to": str(d.get("to", "")).upper(),
                    "summary": str(d.get("summary", "")),
                })

    return ClassifierResult(
        verdict=verdict,
        critical_count=_count("critical_count"),
        high_count=_count("high_count"),
        medium_count=_count("medium_count"),
        low_count=_count("low_count"),
        findings=findings,
        raw_json=parsed,
        error=None,
        elapsed_ms=elapsed_ms,
        downgrades=downgrades,
    )


def _fail_safe(error_code: str, elapsed_ms: int, *, raw_json: dict | None = None) -> ClassifierResult:
    """Return a conservative fail-safe result.

    Any classifier error (timeout, parse, missing field) produces a result
    that CALLERS MUST treat as potentially blocking. The result has
    verdict="fail" and critical_count=1 so that a blind caller will block
    the merge rather than silently pass. Individual gates decide whether
    to actually fail on classifier errors or fall through to a different
    path.
    """
    return ClassifierResult(
        verdict="fail",
        critical_count=1,
        high_count=0,
        medium_count=0,
        low_count=0,
        findings=[],
        raw_json=raw_json or {},
        error=error_code,
        elapsed_ms=elapsed_ms,
    )


def _emit_classifier_event(event_bus: Any, purpose: str, primary_bytes: int, result: ClassifierResult) -> None:
    """Best-effort emit CLASSIFIER_CALL event. Never raises."""
    if event_bus is None:
        return
    try:
        event_bus.emit("CLASSIFIER_CALL", data={
            "purpose": purpose,
            "primary_output_bytes": primary_bytes,
            "verdict": result.verdict,
            "critical_count": result.critical_count,
            "high_count": result.high_count,
            "elapsed_ms": result.elapsed_ms,
            "error": result.error,
        })
    except Exception as exc:
        logger.debug("CLASSIFIER_CALL emit failed: %s", exc)
