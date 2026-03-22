"""Post-phase LLM audit: spec-vs-implementation gap detection.

Migrated from: lib/orchestration/auditor.sh (298 LOC)
Provides: build_audit_prompt(), run_audit(), parse_audit_result()
"""

import json
import logging
import re
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from .subprocess_utils import run_claude_logged, run_command

logger = logging.getLogger(__name__)


# ─── Dataclasses ─────────────────────────────────────────────────


@dataclass
class AuditGap:
    """A single gap found during audit."""

    requirement_id: str = ""
    description: str = ""
    severity: str = "info"  # critical, warning, info
    suggested_fix: str = ""
    spec_reference: str = ""
    suggested_scope: str = ""


@dataclass
class AuditResult:
    """Parsed result from the LLM audit."""

    audit_result: str = "unknown"  # clean, gaps_found, parse_error
    gaps: list[AuditGap] = field(default_factory=list)
    recommendations: list[str] = field(default_factory=list)
    coverage_score: float = 0.0
    summary: str = ""
    duration_ms: int = 0


# ─── Audit Prompt Construction ───────────────────────────────────
# Migrated from: auditor.sh:build_audit_prompt()


def build_audit_prompt(
    state: dict[str, Any],
    cycle: int = 1,
    input_mode: str = "spec",
    input_path: str = "",
    digest_dir: str = "",
) -> dict[str, Any]:
    """Collect merged changes with scopes and file lists for audit.

    Args:
        state: Orchestration state dict.
        cycle: Current audit cycle number.
        input_mode: "spec" or "digest".
        input_path: Path to spec/brief file.
        digest_dir: Path to digest directory.

    Returns:
        Dict suitable for template rendering.
    """
    if not digest_dir:
        try:
            from .paths import SetRuntime
            digest_dir = SetRuntime().digest_dir
        except Exception:
            digest_dir = "wt/orchestration/digest"
    changes = state.get("changes", [])

    # Collect merged changes
    changes_list: list[dict[str, Any]] = []
    for c in changes:
        if c.get("status") == "merged":
            file_list = _get_change_files(c)
            changes_list.append({
                "name": c.get("name", ""),
                "scope": c.get("scope", ""),
                "status": "merged",
                "file_list": file_list,
            })

    # Also include failed/skipped for context
    for c in changes:
        if c.get("status") in ("failed", "skipped"):
            changes_list.append({
                "name": c.get("name", ""),
                "scope": c.get("scope", ""),
                "status": c.get("status", ""),
                "file_list": "",
            })

    # Build input based on mode
    if input_mode == "digest":
        reqs_path = Path(digest_dir) / "requirements.json"
        cov_path = Path(digest_dir) / "coverage.json"

        reqs_json: list[dict] = []
        if reqs_path.is_file():
            try:
                data = json.loads(reqs_path.read_text(encoding="utf-8"))
                reqs_json = [
                    {"id": r.get("id"), "title": r.get("title"), "brief": r.get("brief")}
                    for r in data.get("requirements", [])
                ]
            except (json.JSONDecodeError, OSError):
                pass

        coverage_text = ""
        if cov_path.is_file():
            try:
                cov_data = json.loads(cov_path.read_text(encoding="utf-8"))
                parts = []
                for req_id, entry in cov_data.get("coverage", {}).items():
                    status = entry.get("status", "unknown")
                    change = entry.get("change", "unassigned")
                    parts.append(f"{req_id}: {status} — {change}")
                coverage_text = "\n".join(parts)
            except (json.JSONDecodeError, OSError):
                pass

        return {
            "requirements": reqs_json,
            "changes": changes_list,
            "coverage": coverage_text,
            "mode": "digest",
        }
    else:
        # Spec/brief mode — use raw input text
        spec_text = ""
        if input_path and Path(input_path).is_file():
            try:
                spec_text = Path(input_path).read_text(encoding="utf-8")[:30000]
            except (OSError, IOError):
                pass

        return {
            "spec_text": spec_text,
            "changes": changes_list,
            "mode": "spec",
        }


# ─── Audit Execution ────────────────────────────────────────────
# Migrated from: auditor.sh:run_post_phase_audit()


def run_audit(
    state: dict[str, Any],
    cycle: int = 1,
    input_mode: str = "spec",
    input_path: str = "",
    digest_dir: str = "wt/orchestration/digest",
    review_model: str = "sonnet",
) -> AuditResult:
    """Run post-phase audit: build prompt, call LLM, parse result.

    Args:
        state: Orchestration state dict.
        cycle: Current audit cycle number.
        input_mode: "spec" or "digest".
        input_path: Path to spec/brief file.
        digest_dir: Path to digest directory.
        review_model: Model to use for audit.

    Returns:
        AuditResult with gaps, recommendations, etc.
    """
    start_ms = int(time.time() * 1000)

    logger.info(
        "Post-phase audit starting (cycle %d, mode=%s, model=%s)",
        cycle,
        input_mode,
        review_model,
    )

    # Build prompt input
    audit_input = build_audit_prompt(
        state, cycle, input_mode, input_path, digest_dir
    )

    # Render via set-orch-core template
    import tempfile

    input_file = tempfile.NamedTemporaryFile(
        mode="w", suffix=".json", delete=False
    )
    try:
        json.dump(audit_input, input_file)
        input_file.close()

        template_result = run_command(
            ["set-orch-core", "template", "audit", "--input-file", input_file.name],
            timeout=30,
        )
    finally:
        Path(input_file.name).unlink(missing_ok=True)

    if template_result.exit_code != 0:
        logger.error("Post-phase audit: prompt build failed")
        return AuditResult(
            audit_result="prompt_error",
            duration_ms=int(time.time() * 1000) - start_ms,
        )

    audit_prompt = template_result.stdout

    # Call LLM with timeout
    result = run_claude_logged(
        audit_prompt,
        purpose="audit",
        timeout=1800,
        model=review_model,
    )

    duration_ms = int(time.time() * 1000) - start_ms

    # Write debug log
    try:
        from .paths import SetRuntime
        debug_log = Path(SetRuntime().audit_log(cycle))
    except Exception:
        debug_log = Path(f"wt/orchestration/audit-cycle-{cycle}.log")
    debug_log.parent.mkdir(parents=True, exist_ok=True)
    try:
        debug_log.write_text(
            f"=== AUDIT PROMPT (cycle {cycle}) ===\n{audit_prompt}\n\n"
            f"=== RAW LLM RESPONSE ===\n{result.stdout}\n\n"
            f"=== METADATA ===\nmodel: {review_model}\n"
            f"duration_ms: {duration_ms}\nexit_code: {result.exit_code}\n",
            encoding="utf-8",
        )
    except OSError:
        pass

    if result.exit_code != 0:
        logger.error(
            "Post-phase audit cycle %d: LLM call failed (rc=%d) in %dms",
            cycle,
            result.exit_code,
            duration_ms,
        )
        return AuditResult(
            audit_result="llm_error",
            duration_ms=duration_ms,
        )

    # Parse result
    try:
        parsed = parse_audit_result(result.stdout)
        parsed.duration_ms = duration_ms
        return parsed
    except ValueError as e:
        logger.error("Post-phase audit cycle %d: JSON parse failed: %s", cycle, e)
        return AuditResult(
            audit_result="parse_error",
            summary=result.stdout[:5000],
            duration_ms=duration_ms,
        )


# ─── Audit Result Parsing ───────────────────────────────────────
# Migrated from: auditor.sh:parse_audit_result()


def parse_audit_result(raw_output: str) -> AuditResult:
    """Parse JSON from LLM audit output.

    Tries multiple extraction strategies (same as planner/digest parsers).

    Returns:
        AuditResult with gaps, recommendations.

    Raises:
        ValueError: If JSON cannot be extracted.
    """
    # Strategy 1: direct parse
    try:
        data = json.loads(raw_output)
        if "audit_result" in data:
            return _dict_to_audit_result(data)
    except json.JSONDecodeError:
        pass

    # Strategy 2: strip markdown fences
    stripped = re.sub(r"```(?:json|JSON)?\s*\n?", "", raw_output).strip()
    try:
        data = json.loads(stripped)
        if "audit_result" in data:
            return _dict_to_audit_result(data)
    except json.JSONDecodeError:
        pass

    # Strategy 3: find JSON by braces
    first_brace = raw_output.find("{")
    if first_brace >= 0:
        for j in range(len(raw_output) - 1, first_brace, -1):
            if raw_output[j] == "}":
                try:
                    data = json.loads(raw_output[first_brace : j + 1])
                    if "audit_result" in data:
                        return _dict_to_audit_result(data)
                except json.JSONDecodeError:
                    continue

    raise ValueError("Could not parse audit JSON from LLM output")


def _dict_to_audit_result(data: dict) -> AuditResult:
    """Convert parsed dict to AuditResult."""
    gaps = []
    for g in data.get("gaps", []):
        gaps.append(
            AuditGap(
                requirement_id=g.get("requirement_id", ""),
                description=g.get("description", ""),
                severity=g.get("severity", "info"),
                suggested_fix=g.get("suggested_fix", ""),
                spec_reference=g.get("spec_reference", ""),
                suggested_scope=g.get("suggested_scope", ""),
            )
        )

    return AuditResult(
        audit_result=data.get("audit_result", "unknown"),
        gaps=gaps,
        recommendations=data.get("recommendations", []),
        coverage_score=float(data.get("coverage_score", 0.0)),
        summary=data.get("summary", ""),
    )


# ─── Helpers ─────────────────────────────────────────────────────


def _get_change_files(change: dict[str, Any], max_files: int = 50) -> str:
    """Get file list from a change's merge commit.

    Migrated from: auditor.sh:build_audit_prompt() inline git-diff-tree call.
    """
    merge_commit = change.get("merge_commit", "")
    if not merge_commit:
        return ""

    from .subprocess_utils import run_git

    result = run_git("diff-tree", "--no-commit-id", "--name-only", "-r", merge_commit)
    if result.exit_code == 0:
        lines = result.stdout.strip().splitlines()[:max_files]
        return "\n".join(lines)
    return ""
