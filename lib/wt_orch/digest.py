"""Spec digest engine: scan, classify, extract requirements, validate, track coverage.

Migrated from: lib/orchestration/digest.sh (1,311 LOC)
Provides: scan_spec_directory(), build_digest_prompt(), call_digest_api(),
          write_digest_output(), validate_digest(), stabilize_ids(),
          check_digest_freshness(), populate_coverage(), check_coverage_gaps(),
          update_coverage_status(), generate_triage_md(), parse_triage_md(),
          merge_triage_to_ambiguities(), merge_planner_resolutions()
"""

import hashlib
import json
import logging
import os
import re
import shutil
import tempfile
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from .subprocess_utils import run_claude

logger = logging.getLogger(__name__)

DIGEST_DIR = "wt/orchestration/digest"

# Core ignore patterns for spec scanning
_CORE_IGNORE_PATTERNS = {"archive", ".git", "__pycache__", ".venv"}


def _get_ignore_patterns() -> set:
    """Get ignore patterns from core + profile."""
    from .profile_loader import load_profile

    profile = load_profile()
    return _CORE_IGNORE_PATTERNS | set(profile.ignore_patterns())

# Spec file extensions
_SPEC_EXTENSIONS = {".md", ".yaml", ".yml", ".txt"}

# Master file detection names
_MASTER_NAMES = {"README.md", "index.md", "spec.md", "main.md", "overview.md"}


# ─── Dataclasses ──────────────────────────────────────────────────


@dataclass
class SpecFile:
    """A single spec file found during scanning."""

    path: str
    size_bytes: int
    content: str


@dataclass
class ScanResult:
    """Result of scanning a spec directory."""

    file_count: int
    source_hash: str
    master_file: str  # empty string if none
    spec_base_dir: str
    files: list[str]  # relative paths


@dataclass
class DigestResult:
    """Parsed result from the LLM digest call."""

    file_classifications: dict[str, str] = field(default_factory=dict)
    conventions: dict[str, Any] = field(default_factory=lambda: {"categories": []})
    data_definitions: str = ""
    requirements: list[dict[str, Any]] = field(default_factory=list)
    domains: list[dict[str, Any]] = field(default_factory=list)
    dependencies: list[dict[str, Any]] = field(default_factory=list)
    ambiguities: list[dict[str, Any]] = field(default_factory=list)
    execution_hints: dict[str, Any] = field(default_factory=dict)


# ─── Spec Directory Scanning ─────────────────────────────────────
# Migrated from: digest.sh:scan_spec_directory()


def scan_spec_directory(spec_path: str | Path) -> ScanResult:
    """Recursively scan a spec directory or single file for spec files.

    Args:
        spec_path: Path to spec directory or single file.

    Returns:
        ScanResult with file list, hash, and master file detection.

    Raises:
        FileNotFoundError: If spec_path doesn't exist.
    """
    path = Path(spec_path)
    if not path.exists():
        raise FileNotFoundError(f"Spec path not found: {spec_path}")

    files: list[Path] = []

    if path.is_file():
        files = [path]
    else:
        files = _find_spec_files(path)

    if not files:
        raise FileNotFoundError(f"No spec files found in: {spec_path}")

    # Sort for deterministic hashing
    files.sort()

    # Detect master file
    master_file = ""
    if path.is_dir():
        for f in files:
            rel = f.relative_to(path)
            # Only root-level files
            if len(rel.parts) > 1:
                continue
            if f.name in _MASTER_NAMES:
                master_file = str(rel)
                break
            # v*-*.md pattern (e.g., v1-craftbrew.md)
            if re.match(r"^v\d+-.*\.md$", f.name):
                master_file = str(rel)
                break

    # Compute combined SHA256
    h = hashlib.sha256()
    for f in files:
        h.update(f.read_bytes())
    source_hash = h.hexdigest()

    # Build relative file list
    rel_files: list[str] = []
    for f in files:
        if path.is_dir():
            rel_files.append(str(f.relative_to(path)))
        else:
            rel_files.append(f.name)

    return ScanResult(
        file_count=len(files),
        source_hash=source_hash,
        master_file=master_file,
        spec_base_dir=str(path),
        files=rel_files,
    )


def _find_spec_files(directory: Path) -> list[Path]:
    """Recursively find spec files, skipping ignore patterns."""
    result: list[Path] = []
    for item in sorted(directory.rglob("*")):
        if not item.is_file():
            continue
        # Check ignore patterns against all parent parts
        parts = item.relative_to(directory).parts
        if any(p in _get_ignore_patterns() for p in parts):
            continue
        if item.suffix.lower() in _SPEC_EXTENSIONS:
            result.append(item)
    return result


# ─── Prompt Construction ─────────────────────────────────────────
# Migrated from: digest.sh:build_digest_prompt()


def build_digest_prompt(spec_path: str | Path, scan_result: ScanResult) -> str:
    """Assemble the LLM prompt from spec files and scan context.

    Args:
        spec_path: Path to spec directory or single file.
        scan_result: Result from scan_spec_directory().

    Returns:
        Complete prompt string ready for Claude API call.
    """
    path = Path(spec_path)
    spec_content = ""

    # Master file first if present
    if scan_result.master_file:
        master_path = (
            path if path.is_file() else path / scan_result.master_file
        )
        if master_path.is_file():
            spec_content += f"=== FILE: {scan_result.master_file} ===\n"
            spec_content += master_path.read_text(encoding="utf-8", errors="replace")
            spec_content += "\n\n"

    # Remaining files
    for rel_file in scan_result.files:
        if rel_file == scan_result.master_file:
            continue
        full_path = path if path.is_file() else path / rel_file
        if full_path.is_file():
            spec_content += f"=== FILE: {rel_file} ===\n"
            spec_content += full_path.read_text(encoding="utf-8", errors="replace")
            spec_content += "\n\n"

    return _DIGEST_PROMPT_TEMPLATE.replace("{{SPEC_CONTENT}}", spec_content)


# ─── API Call ────────────────────────────────────────────────────
# Migrated from: digest.sh:call_digest_api()


def call_digest_api(prompt: str, model: str = "opus", max_retries: int = 3) -> str:
    """Call Claude CLI with the digest prompt.

    Args:
        prompt: The assembled digest prompt.
        model: Model name to use.
        max_retries: Maximum retry attempts.

    Returns:
        Raw LLM response string.

    Raises:
        RuntimeError: If all retries fail.
    """
    for attempt in range(1, max_retries + 1):
        result = run_claude(
            prompt,
            timeout=600,
            model=model,
            extra_args=["--max-turns", "3"],
        )
        if result.exit_code == 0 and result.stdout.strip():
            return result.stdout
        logger.warning(
            "Digest API attempt %d/%d failed (rc=%d)",
            attempt,
            max_retries,
            result.exit_code,
        )
    raise RuntimeError(f"Digest API call failed after {max_retries} attempts")


def parse_digest_response(raw_response: str) -> DigestResult:
    """Parse JSON from LLM digest output.

    Migrated from: digest.sh:parse_digest_response()

    Tries multiple extraction strategies:
    1. Direct JSON parse
    2. Strip markdown fences
    3. Find JSON by scanning braces

    Returns:
        Parsed DigestResult.

    Raises:
        ValueError: If JSON cannot be extracted.
    """
    # Strategy 1: direct parse
    try:
        data = json.loads(raw_response)
        if "requirements" in data:
            return _dict_to_digest_result(data)
    except json.JSONDecodeError:
        pass

    # Strategy 2: strip markdown fences
    stripped = re.sub(r"```(?:json|JSON)?\s*\n?", "", raw_response).strip()
    try:
        data = json.loads(stripped)
        if "requirements" in data:
            return _dict_to_digest_result(data)
    except json.JSONDecodeError:
        pass

    # Strategy 3: find JSON by braces
    first_brace = raw_response.find("{")
    if first_brace >= 0:
        for j in range(len(raw_response) - 1, first_brace, -1):
            if raw_response[j] == "}":
                try:
                    data = json.loads(raw_response[first_brace : j + 1])
                    if "requirements" in data:
                        return _dict_to_digest_result(data)
                except json.JSONDecodeError:
                    continue

    raise ValueError("Could not parse digest JSON from LLM output")


def _dict_to_digest_result(data: dict) -> DigestResult:
    """Convert a parsed dict to DigestResult."""
    return DigestResult(
        file_classifications=data.get("file_classifications", {}),
        conventions=data.get("conventions", {"categories": []}),
        data_definitions=data.get("data_definitions", ""),
        requirements=data.get("requirements", []),
        domains=data.get("domains", []),
        dependencies=data.get("dependencies", []),
        ambiguities=data.get("ambiguities", []),
        execution_hints=data.get("execution_hints", {}),
    )


# ─── Output Writing ──────────────────────────────────────────────
# Migrated from: digest.sh:write_digest_output()


def write_digest_output(
    digest: DigestResult,
    scan_result: ScanResult,
    digest_dir: str = DIGEST_DIR,
) -> None:
    """Write digest output files atomically.

    Creates: index.json, conventions.json, data-definitions.md,
    requirements.json, dependencies.json, ambiguities.json,
    triage.md (if ambiguities), coverage.json, domains/*.md

    Args:
        digest: Parsed digest result.
        scan_result: Scan result for metadata.
        digest_dir: Output directory path.
    """
    from datetime import datetime, timezone

    tmp_dir = tempfile.mkdtemp()
    try:
        # index.json
        index = {
            "spec_base_dir": scan_result.spec_base_dir,
            "source_hash": scan_result.source_hash,
            "file_count": scan_result.file_count,
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "files": scan_result.files,
            "file_classifications": digest.file_classifications,
            "execution_hints": digest.execution_hints,
        }
        _write_json(Path(tmp_dir) / "index.json", index)

        # conventions.json
        _write_json(Path(tmp_dir) / "conventions.json", digest.conventions)

        # data-definitions.md
        (Path(tmp_dir) / "data-definitions.md").write_text(
            digest.data_definitions or "No data definitions found.",
            encoding="utf-8",
        )

        # requirements.json
        _write_json(
            Path(tmp_dir) / "requirements.json",
            {"requirements": digest.requirements},
        )

        # dependencies.json
        _write_json(
            Path(tmp_dir) / "dependencies.json",
            {"dependencies": digest.dependencies},
        )

        # ambiguities.json
        _write_json(
            Path(tmp_dir) / "ambiguities.json",
            {"ambiguities": digest.ambiguities},
        )

        # triage.md (only when ambiguities exist)
        if digest.ambiguities:
            existing_triage = Path(digest_dir) / "triage.md"
            existing_path = str(existing_triage) if existing_triage.is_file() else None
            generate_triage_md(
                digest.ambiguities,
                str(Path(tmp_dir) / "triage.md"),
                existing_path,
            )

        # coverage.json (preserve existing or create skeleton)
        cov_path = Path(digest_dir) / "coverage.json"
        if cov_path.is_file():
            shutil.copy2(str(cov_path), str(Path(tmp_dir) / "coverage.json"))
        else:
            _write_json(
                Path(tmp_dir) / "coverage.json",
                {"coverage": {}, "uncovered": []},
            )

        # domains/*.md
        domains_dir = Path(tmp_dir) / "domains"
        domains_dir.mkdir(exist_ok=True)
        for domain in digest.domains:
            name = domain.get("name", "unknown")
            summary = domain.get("summary", "")
            (domains_dir / f"{name}.md").write_text(summary, encoding="utf-8")

        # Atomic move to final location
        dest = Path(digest_dir)
        dest.parent.mkdir(parents=True, exist_ok=True)
        if dest.is_dir():
            # Preserve coverage.json if not already copied
            old_cov = dest / "coverage.json"
            tmp_cov = Path(tmp_dir) / "coverage.json"
            if old_cov.is_file() and not tmp_cov.is_file():
                shutil.copy2(str(old_cov), str(tmp_cov))
            shutil.rmtree(str(dest))
        shutil.move(tmp_dir, str(dest))
        logger.info("Digest output written to %s", digest_dir)

    except Exception:
        # Cleanup temp dir on error
        shutil.rmtree(tmp_dir, ignore_errors=True)
        raise


# ─── ID Stabilization ───────────────────────────────────────────
# Migrated from: digest.sh:stabilize_ids()


def stabilize_ids(
    new_digest: DigestResult,
    digest_dir: str = DIGEST_DIR,
) -> DigestResult:
    """Preserve requirement IDs across re-digests by source+section matching.

    Args:
        new_digest: Freshly parsed digest.
        digest_dir: Path to existing digest directory.

    Returns:
        DigestResult with stabilized IDs (existing IDs preserved, removed tracked).
    """
    old_reqs_path = Path(digest_dir) / "requirements.json"
    if not old_reqs_path.is_file():
        return new_digest

    try:
        old_data = json.loads(old_reqs_path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return new_digest

    old_reqs = old_data.get("requirements", [])
    old_by_key: dict[tuple[str, str], dict] = {}
    for r in old_reqs:
        key = (r.get("source", ""), r.get("source_section", ""))
        old_by_key[key] = r

    used_ids: set[str] = set()
    stabilized: list[dict] = []

    # Match new requirements against existing by source + source_section
    for req in new_digest.requirements:
        key = (req.get("source", ""), req.get("source_section", ""))
        if key in old_by_key:
            req["id"] = old_by_key[key]["id"]
        if "id" not in req:
            continue  # skip requirements without IDs (will be assigned below)
        used_ids.add(req["id"])
        stabilized.append(req)

    # Track domain counters for potential new ID assignment
    domain_counters: dict[str, int] = {}
    for req in stabilized:
        parts = req["id"].split("-")
        if len(parts) >= 3:
            domain = parts[1]
            try:
                num = int(parts[2])
                domain_counters[domain] = max(domain_counters.get(domain, 0), num)
            except ValueError:
                pass

    # Mark removed requirements
    for old_req in old_reqs:
        if old_req["id"] not in used_ids:
            removed = dict(old_req)
            removed["status"] = "removed"
            stabilized.append(removed)

    new_digest.requirements = stabilized
    return new_digest


# ─── Validation ──────────────────────────────────────────────────
# Migrated from: digest.sh:validate_digest()


def validate_digest(digest: DigestResult | dict) -> list[str]:
    """Check structural integrity of a digest.

    Args:
        digest: DigestResult or raw parsed dict.

    Returns:
        List of validation error strings (empty = valid).
    """
    if isinstance(digest, DigestResult):
        data = {
            "requirements": digest.requirements,
            "conventions": digest.conventions,
            "domains": digest.domains,
            "dependencies": digest.dependencies,
        }
    else:
        data = digest

    errors: list[str] = []
    reqs = data.get("requirements", [])

    # Check requirement ID format
    for req in reqs:
        req_id = req.get("id", "")
        if not re.match(r"^REQ-[A-Z0-9]+-[0-9]+$", req_id):
            errors.append(f"Invalid requirement ID format: {req_id}")

    # Check for duplicate IDs
    ids = [r.get("id", "") for r in reqs]
    seen: set[str] = set()
    for rid in ids:
        if rid in seen:
            errors.append(f"Duplicate requirement ID: {rid}")
        seen.add(rid)

    # Check conventions exist
    if not data.get("conventions"):
        errors.append("Missing or invalid conventions")

    # Check domains exist for referenced domains
    req_domains = {r.get("domain", "") for r in reqs if r.get("domain")}
    digest_domains = {d.get("name", "") for d in data.get("domains", [])}
    for rd in sorted(req_domains):
        if rd and rd not in digest_domains:
            errors.append(
                f"Domain '{rd}' referenced in requirements but no domain summary exists"
            )

    # Check dependency references
    all_req_ids = {r.get("id", "") for r in reqs}
    for dep in data.get("dependencies", []):
        for ref_field in ("from", "to"):
            ref = dep.get(ref_field, "")
            if ref and ref not in all_req_ids:
                errors.append(
                    f"Dependency references non-existent requirement: {ref}"
                )

    # Check cross-cutting requirements have affects_domains
    for req in reqs:
        if req.get("cross_cutting") and not req.get("affects_domains"):
            errors.append(
                f"Cross-cutting requirement missing affects_domains: {req.get('id')}"
            )

    # Warn if acceptance_criteria field is absent (old digest or LLM omission)
    reqs_without_ac = [
        r.get("id", "?") for r in reqs
        if "acceptance_criteria" not in r
    ]
    if reqs_without_ac and reqs:
        errors.append(
            f"[WARN] {len(reqs_without_ac)} requirements missing acceptance_criteria field "
            f"(first: {reqs_without_ac[0]}). Old digest or LLM omission — non-blocking."
        )

    return errors


# ─── Coverage Tracking ───────────────────────────────────────────
# Migrated from: digest.sh:populate_coverage(), check_coverage_gaps(),
#                update_coverage_status(), final_coverage_check()


def populate_coverage(
    plan_data: dict,
    digest_dir: str = DIGEST_DIR,
) -> dict[str, Any]:
    """Map requirements to plan changes. Write coverage.json.

    Args:
        plan_data: Parsed plan JSON with .changes[].
        digest_dir: Path to digest directory.

    Returns:
        Coverage dict {req_id: {change, status, ...}}.
    """
    reqs_path = Path(digest_dir) / "requirements.json"
    if not reqs_path.is_file():
        logger.warning("populate_coverage: no requirements.json — skipping")
        return {}

    coverage: dict[str, Any] = {}

    changes = plan_data.get("changes", [])
    for change in changes:
        change_name = change.get("name", "")

        # Primary owned requirements
        for req_id in change.get("requirements", []):
            coverage[req_id] = {"change": change_name, "status": "planned"}

        # Cross-cutting (also_affects_reqs)
        for req_id in change.get("also_affects_reqs", []):
            if req_id in coverage:
                also = coverage[req_id].get("also_affects", [])
                if change_name not in also:
                    also.append(change_name)
                coverage[req_id]["also_affects"] = also

    # Restore previously-merged requirements from persistent history
    merged_history_path = Path(digest_dir) / "coverage-merged.json"
    if merged_history_path.is_file():
        try:
            prev = json.loads(merged_history_path.read_text(encoding="utf-8"))
            restored = 0
            for prev_id, prev_entry in prev.items():
                if prev_id not in coverage:
                    entry = dict(prev_entry)
                    entry["phase"] = "previous"
                    coverage[prev_id] = entry
                    restored += 1
            if restored:
                logger.info(
                    "Restored %d previously-merged requirements from history",
                    restored,
                )
        except (json.JSONDecodeError, OSError):
            pass

    # Compute uncovered
    uncovered = check_coverage_gaps_internal(coverage, digest_dir)

    # Write coverage.json
    cov_path = Path(digest_dir) / "coverage.json"
    _write_json(cov_path, {"coverage": coverage, "uncovered": uncovered})

    covered_count = len(coverage)
    logger.info("Coverage populated: %d requirements mapped", covered_count)

    return coverage


def check_coverage_gaps(digest_dir: str = DIGEST_DIR) -> list[str]:
    """Identify uncovered requirements. Updates coverage.json.

    Returns:
        List of uncovered requirement IDs.
    """
    cov_path = Path(digest_dir) / "coverage.json"
    reqs_path = Path(digest_dir) / "requirements.json"
    if not cov_path.is_file() or not reqs_path.is_file():
        return []

    try:
        cov_data = json.loads(cov_path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return []

    coverage = cov_data.get("coverage", {})
    uncovered = check_coverage_gaps_internal(coverage, digest_dir)

    if uncovered:
        cov_data["uncovered"] = uncovered
        _write_json(cov_path, cov_data)
        logger.warning("%d uncovered requirement(s)", len(uncovered))

    return uncovered


def check_coverage_gaps_internal(
    coverage: dict[str, Any],
    digest_dir: str = DIGEST_DIR,
) -> list[str]:
    """Compute uncovered requirement IDs.

    Migrated from: digest.sh:check_coverage_gaps_internal()
    """
    reqs_path = Path(digest_dir) / "requirements.json"
    if not reqs_path.is_file():
        return []

    try:
        reqs_data = json.loads(reqs_path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return []

    all_ids = [
        r["id"]
        for r in reqs_data.get("requirements", [])
        if r.get("status") != "removed"
    ]
    covered_ids = set(coverage.keys())

    return [rid for rid in all_ids if rid not in covered_ids]


def final_coverage_check(digest_dir: str = DIGEST_DIR) -> str:
    """Read digest requirements, compute covered/uncovered counts, return summary.

    Called before marking orchestration done. Result included in summary email.

    Args:
        digest_dir: Path to digest directory.

    Returns:
        Human-readable summary string (e.g., "12/15 requirements covered (3 uncovered)").
        Empty string if no digest data available.
    """
    reqs_path = Path(digest_dir) / "requirements.json"
    cov_path = Path(digest_dir) / "coverage.json"

    if not reqs_path.is_file():
        return ""

    try:
        reqs_data = json.loads(reqs_path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return ""

    all_reqs = [
        r for r in reqs_data.get("requirements", [])
        if r.get("status") != "removed"
    ]
    total = len(all_reqs)
    if total == 0:
        return ""

    # Read coverage data
    coverage: dict = {}
    if cov_path.is_file():
        try:
            cov_data = json.loads(cov_path.read_text(encoding="utf-8"))
            coverage = cov_data.get("coverage", {})
        except (json.JSONDecodeError, OSError):
            pass

    covered = sum(
        1 for r in all_reqs
        if r["id"] in coverage and coverage[r["id"]].get("status") == "merged"
    )
    planned = sum(
        1 for r in all_reqs
        if r["id"] in coverage and coverage[r["id"]].get("status") != "merged"
    )
    uncovered_ids = [r["id"] for r in all_reqs if r["id"] not in coverage]

    lines = [f"{covered}/{total} requirements covered (merged)"]
    if planned:
        lines.append(f"  {planned} planned but not yet merged")
    if uncovered_ids:
        lines.append(f"  {len(uncovered_ids)} uncovered: {', '.join(uncovered_ids[:10])}")
        if len(uncovered_ids) > 10:
            lines[-1] += f" (+{len(uncovered_ids) - 10} more)"

    summary = "\n".join(lines)
    logger.info("Final coverage check: %s", lines[0])
    return summary


def update_coverage_status(
    change_name: str,
    new_status: str,
    digest_dir: str = DIGEST_DIR,
) -> None:
    """Update coverage status for all requirements owned by a change.

    Migrated from: digest.sh:update_coverage_status()

    Args:
        change_name: Name of the change.
        new_status: New status string (e.g., "dispatched", "merged").
        digest_dir: Path to digest directory.
    """
    cov_path = Path(digest_dir) / "coverage.json"
    if not cov_path.is_file():
        return

    try:
        cov_data = json.loads(cov_path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return

    coverage = cov_data.get("coverage", {})
    for req_id, entry in coverage.items():
        if entry.get("change") == change_name:
            entry["status"] = new_status

    cov_data["coverage"] = coverage
    _write_json(cov_path, cov_data)

    # Persist merged requirements to history
    if new_status == "merged":
        merged_history = Path(digest_dir) / "coverage-merged.json"
        merged_entries = {
            k: v for k, v in coverage.items() if v.get("change") == change_name
        }
        if merged_history.is_file():
            try:
                existing = json.loads(merged_history.read_text(encoding="utf-8"))
                existing.update(merged_entries)
                _write_json(merged_history, existing)
            except (json.JSONDecodeError, OSError):
                _write_json(merged_history, merged_entries)
        else:
            _write_json(merged_history, merged_entries)

    logger.info("Coverage status updated: %s → %s", change_name, new_status)


def reconcile_coverage(state_file: str, digest_dir: str = DIGEST_DIR) -> int:
    """Sync coverage.json with actual change statuses from state.

    For each requirement in coverage.json, if its owning change is 'merged'
    in the state file but the coverage status is anything other than 'merged',
    update it. Writes to coverage-merged.json via read-merge-write.

    Returns number of requirements fixed. Returns 0 if coverage.json
    doesn't exist (no-digest mode).
    """
    cov_path = Path(digest_dir) / "coverage.json"
    if not cov_path.is_file():
        return 0

    # Load coverage
    try:
        cov_data = json.loads(cov_path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return 0

    # Load state to get change statuses
    state_path = Path(state_file)
    if not state_path.is_file():
        return 0
    try:
        state_data = json.loads(state_path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return 0

    # Build change_name → status lookup
    change_statuses: dict[str, str] = {}
    for change in state_data.get("changes", []):
        name = change.get("name", "")
        status = change.get("status", "")
        if name:
            change_statuses[name] = status

    # Reconcile: find requirements whose change is merged but coverage isn't
    coverage = cov_data.get("coverage", {})
    fixed_count = 0
    fixed_entries: dict[str, Any] = {}

    for req_id, entry in coverage.items():
        owning_change = entry.get("change", "")
        if not owning_change:
            continue
        if change_statuses.get(owning_change) == "merged" and entry.get("status") != "merged":
            entry["status"] = "merged"
            fixed_count += 1
            fixed_entries[req_id] = entry

    if fixed_count == 0:
        return 0

    # Write updated coverage.json
    cov_data["coverage"] = coverage
    _write_json(cov_path, cov_data)

    # Merge into coverage-merged.json (read-merge-write)
    merged_history = Path(digest_dir) / "coverage-merged.json"
    if merged_history.is_file():
        try:
            existing = json.loads(merged_history.read_text(encoding="utf-8"))
            existing.update(fixed_entries)
            _write_json(merged_history, existing)
        except (json.JSONDecodeError, OSError):
            _write_json(merged_history, fixed_entries)
    else:
        _write_json(merged_history, fixed_entries)

    logger.warning(
        "Coverage reconciliation: fixed %d requirements with stale status", fixed_count
    )
    return fixed_count


# ─── Triage Pipeline ────────────────────────────────────────────
# Migrated from: digest.sh:generate_triage_md(), parse_triage_md(),
#                merge_triage_to_ambiguities(), merge_planner_resolutions()


def generate_triage_md(
    ambiguities: list[dict],
    output_path: str,
    existing_triage_path: str | None = None,
) -> None:
    """Generate triage.md from ambiguities for human review.

    Migrated from: digest.sh:generate_triage_md()
    """
    if not ambiguities:
        return

    # Parse existing decisions if file exists
    existing_decisions: dict[str, dict] = {}
    if existing_triage_path and Path(existing_triage_path).is_file():
        existing_decisions = parse_triage_md(existing_triage_path)

    current_ids = {a.get("id", "") for a in ambiguities}

    lines: list[str] = [
        "# Ambiguity Triage",
        "<!-- Generated by wt-orchestrate digest — edit decisions, then re-run plan -->",
        "",
        "## Instructions",
        "For each ambiguity, set the **Decision** to one of:",
        "- `fix` — spec needs correction before planning (blocks pipeline until fixed and re-digested)",
        "- `defer` — planner will decide during change design",
        "- `ignore` — not relevant or out of scope",
        "",
        "---",
        "",
    ]

    # Render current ambiguities
    for amb in ambiguities:
        amb_id = amb.get("id", "")
        amb_type = amb.get("type", "")
        amb_source = amb.get("source", "unknown")
        amb_section = amb.get("section", "unknown")
        amb_desc = amb.get("description", "")
        amb_affects = ", ".join(amb.get("affects_requirements", []))

        prev = existing_decisions.get(amb_id, {})
        prev_decision = prev.get("decision", "")
        prev_note = prev.get("note", "")

        lines.append(f"### {amb_id} [{amb_type}]")
        lines.append(f"**Source:** {amb_source} § {amb_section}")
        lines.append(f"**Description:** {amb_desc}")
        if amb_affects:
            lines.append(f"**Affects:** {amb_affects}")
        lines.append("")
        lines.append(f"**Decision:** {prev_decision}")
        lines.append(f"**Note:** {prev_note}")
        lines.append("")
        lines.append("---")
        lines.append("")

    # Append removed entries
    for old_id, old_data in existing_decisions.items():
        if old_id not in current_ids:
            lines.append(f"### {old_id} [REMOVED]")
            lines.append(f"**Decision:** {old_data.get('decision', '')}")
            lines.append(f"**Note:** {old_data.get('note', '')}")
            lines.append("")
            lines.append("---")
            lines.append("")

    Path(output_path).write_text("\n".join(lines), encoding="utf-8")


def parse_triage_md(triage_path: str) -> dict[str, dict[str, str]]:
    """Parse triage.md — extract decisions and notes per AMB ID.

    Migrated from: digest.sh:parse_triage_md()

    Returns:
        Dict {amb_id: {"decision": str, "note": str}}.
        Invalid decisions (not fix/defer/ignore) are treated as blank.
        [REMOVED] entries are skipped.
    """
    path = Path(triage_path)
    if not path.is_file():
        return {}

    content = path.read_text(encoding="utf-8")
    result: dict[str, dict[str, str]] = {}

    sections = re.split(r"^### ", content, flags=re.MULTILINE)
    for section in sections:
        if not section.strip():
            continue

        # Parse AMB ID and check for [REMOVED]
        header_match = re.match(r"(AMB-\d+)\s*\[([^\]]+)\]", section)
        if not header_match:
            continue

        amb_id = header_match.group(1)
        tag = header_match.group(2)

        if tag == "REMOVED":
            continue

        # Extract decision
        decision_match = re.search(
            r"\*\*Decision:\*\*\s*(.*?)$", section, re.MULTILINE
        )
        decision = decision_match.group(1).strip() if decision_match else ""

        # Validate decision
        if decision not in ("fix", "defer", "ignore"):
            decision = ""

        # Extract note
        note_match = re.search(r"\*\*Note:\*\*\s*(.*?)$", section, re.MULTILINE)
        note = note_match.group(1).strip() if note_match else ""

        result[amb_id] = {"decision": decision, "note": note}

    return result


def merge_triage_to_ambiguities(
    ambiguities_path: str,
    triage_decisions: dict[str, dict[str, str]],
    resolved_by: str = "triage",
) -> None:
    """Merge triage decisions into ambiguities.json.

    Migrated from: digest.sh:merge_triage_to_ambiguities()
    """
    path = Path(ambiguities_path)
    if not path.is_file():
        return

    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return

    resolution_map = {"fix": "fixed", "defer": "deferred", "ignore": "ignored"}

    for amb in data.get("ambiguities", []):
        amb_id = amb.get("id", "")
        if amb_id in triage_decisions:
            decision = triage_decisions[amb_id].get("decision", "")
            if decision:
                amb["resolution"] = resolution_map.get(decision, decision)
                amb["resolution_note"] = triage_decisions[amb_id].get("note", "")
                amb["resolved_by"] = resolved_by

    _write_json(path, data)


def merge_planner_resolutions(
    ambiguities_path: str,
    plan_path: str,
) -> None:
    """Merge planner resolved_ambiguities back into ambiguities.json.

    Migrated from: digest.sh:merge_planner_resolutions()
    """
    amb_path = Path(ambiguities_path)
    plan_file = Path(plan_path)

    if not amb_path.is_file() or not plan_file.is_file():
        return

    try:
        amb_data = json.loads(amb_path.read_text(encoding="utf-8"))
        plan_data = json.loads(plan_file.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return

    # Collect all resolved_ambiguities from plan changes
    resolutions: list[dict] = []
    for change in plan_data.get("changes", []):
        for ra in change.get("resolved_ambiguities", []):
            resolutions.append(ra)

    if not resolutions:
        return

    res_by_id = {r["id"]: r for r in resolutions if "id" in r}

    for amb in amb_data.get("ambiguities", []):
        amb_id = amb.get("id", "")
        if amb_id in res_by_id:
            res = res_by_id[amb_id]
            amb["resolution"] = "planner-resolved"
            amb["resolution_note"] = res.get("resolution_note", "")
            amb["resolved_by"] = "planner"

    _write_json(amb_path, amb_data)


# ─── Freshness Check ────────────────────────────────────────────
# Migrated from: digest.sh:check_digest_freshness()


def check_digest_freshness(
    spec_path: str | Path,
    digest_dir: str = DIGEST_DIR,
) -> str:
    """Compare spec content hash vs stored digest hash.

    Args:
        spec_path: Path to spec directory or file.
        digest_dir: Path to existing digest directory.

    Returns:
        "fresh", "stale", "missing", or "error".
    """
    index_path = Path(digest_dir) / "index.json"
    if not index_path.is_file():
        return "missing"

    try:
        index_data = json.loads(index_path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return "error"

    stored_hash = index_data.get("source_hash", "")

    try:
        current_scan = scan_spec_directory(spec_path)
    except (FileNotFoundError, OSError):
        return "error"

    return "fresh" if stored_hash == current_scan.source_hash else "stale"


# ─── Orchestration Entry Point ───────────────────────────────────
# Migrated from: digest.sh:cmd_digest()


@dataclass
class DigestRunResult:
    """Result from run_digest() orchestration."""

    ok: bool
    file_count: int = 0
    req_count: int = 0
    domain_count: int = 0
    source_hash: str = ""
    error: str = ""
    validation_warnings: list[str] = field(default_factory=list)


def run_digest(
    spec_path: str,
    *,
    digest_dir: str = DIGEST_DIR,
    model: str = "opus",
    dry_run: bool = False,
) -> DigestRunResult:
    """Run the full digest pipeline: scan → prompt → API call → parse → validate → write.

    Migrated from: digest.sh:cmd_digest()

    Args:
        spec_path: Path to spec directory or single file.
        digest_dir: Output directory for digest files.
        model: Model name for Claude API call.
        dry_run: If True, parse and validate but don't write files.

    Returns:
        DigestRunResult with status and counts.
    """
    # 1. Scan spec files
    try:
        scan = scan_spec_directory(spec_path)
    except FileNotFoundError as e:
        return DigestRunResult(ok=False, error=str(e))

    logger.info(
        "Scanned %d spec file(s), hash=%s", scan.file_count, scan.source_hash
    )
    if scan.master_file:
        logger.info("Master file: %s", scan.master_file)

    # 2. Build prompt
    prompt = build_digest_prompt(spec_path, scan)

    # 3. Call Claude API
    logger.info("Calling Claude for digest generation...")
    try:
        raw_response = call_digest_api(prompt, model=model)
    except RuntimeError as e:
        return DigestRunResult(ok=False, error=str(e))

    # Save raw response for debugging
    debug_path = Path(".claude/digest-last-response.txt")
    debug_path.parent.mkdir(parents=True, exist_ok=True)
    try:
        debug_path.write_text(raw_response, encoding="utf-8")
    except OSError:
        pass

    # 4. Parse response
    try:
        digest = parse_digest_response(raw_response)
    except ValueError as e:
        return DigestRunResult(ok=False, error=str(e))

    # 5. Stabilize IDs (if existing digest present)
    if not dry_run:
        digest = stabilize_ids(digest, digest_dir)

    # 6. Validate
    warnings = validate_digest(digest)

    # 7. Write output or return dry-run result
    if dry_run:
        return DigestRunResult(
            ok=True,
            file_count=scan.file_count,
            req_count=len(digest.requirements),
            domain_count=len(digest.domains),
            source_hash=scan.source_hash,
            validation_warnings=warnings,
        )

    write_digest_output(digest, scan, digest_dir)

    logger.info(
        "Digest complete: %d requirements across %d domain(s)",
        len(digest.requirements),
        len(digest.domains),
    )

    return DigestRunResult(
        ok=True,
        file_count=scan.file_count,
        req_count=len(digest.requirements),
        domain_count=len(digest.domains),
        source_hash=scan.source_hash,
        validation_warnings=warnings,
    )


# ─── Helpers ─────────────────────────────────────────────────────


def _write_json(path: Path, data: Any) -> None:
    """Write JSON data to file with consistent formatting."""
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(data, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )


# ─── Digest Prompt Template ─────────────────────────────────────

_DIGEST_PROMPT_TEMPLATE = """You are a technical analyst processing a product specification into a structured digest for an orchestration system.

## Specification Files

{{SPEC_CONTENT}}

## Instructions

Analyze ALL specification files above and produce a structured digest. Follow these rules precisely:

### 1. File Classification
Classify each file as one of:
- **convention**: Project-wide rules that apply to every change (i18n routing, SEO patterns, design system tokens, naming conventions)
- **feature**: Behavioral requirements for specific functionality (cart operations, user registration, admin CRUD)
- **data**: Entity definitions, catalogs, seed data with attributes (product lists, user roles, categories). Individual data entries are NOT requirements.
- **execution**: Implementation plans, change scoping, dependency graphs, verification checklists

Heuristic:
- Files defining rules/patterns that span multiple features → convention
- Files describing what a specific feature does (behaviors, user stories, flows) → feature
- Files listing entities, items, or seed data with attributes → data
- Files describing implementation order, change scope, or acceptance checklists → execution

### 2. Requirement Extraction
From files classified as **feature**, extract discrete, independently testable requirements.

**Granularity**: One requirement = one independently testable behavior. If it needs its own test case, it is a separate requirement. "Cart supports coupons" is too broad; "ELSO10 coupon gives 10% on first order only" is the right granularity.

**REQUIREMENT GRANULARITY RULES:**
- Each requirement MUST describe exactly ONE testable behavior
- CRUD operations on an entity = minimum 4 separate requirements (create, read, update, delete)
- If a spec section lists multiple distinct user actions, create one REQ per action
- Edge cases and error handling explicitly mentioned in spec = separate requirements
- Compound descriptions like "Users can X and Y" = TWO requirements, not one
- A requirement is too coarse if you cannot write a single test for it without covering multiple independent behaviors

**ID format**: REQ-{DOMAIN_SHORT}-{NNN} (e.g., REQ-CART-001, REQ-SUB-003)

Each requirement must have: id, title, source (file path), source_section (heading), domain, brief (1-2 sentence summary), acceptance_criteria (array of up to 5 concrete, verifiable condition strings).

**Acceptance Criteria extraction**: For each requirement, extract up to 5 concrete, verifiable acceptance criteria from spec scenarios — HTTP contracts (e.g., "POST /api/cart/items → 201 with cartItemId"), state assertions (e.g., "Stock decremented by quantity"), error responses (e.g., "Returns 400 if quantity > stock"). Use `[]` if no explicit testable conditions are found in the spec. The 5-item cap is per-requirement, not counted toward the requirements total.

**Cross-cutting requirements**: Requirements that span multiple features (i18n integration, responsive layout, auth checks) get `cross_cutting: true` and `affects_domains: ["domain1", "domain2"]`.

### 3. De-duplication
If a master file contains a verification checklist or acceptance criteria that restates requirements from feature files, do NOT create duplicate REQ-* IDs. Each unique behavior gets exactly one ID, sourced from the most detailed description.

### 4. Embedded Behavioral Rules
Data files (catalogs, seed data) may contain embedded behavioral rules (business logic, calculations, validation rules, state machines). Extract these as separate REQ-* IDs even though the file is classified as data. Individual data entries (each product, each item) are NOT requirements.

### 5. Convention Extraction
From files classified as **convention** (and convention-like sections in mixed files), extract project-wide rules into a conventions structure.

### 6. Data Definitions
From files classified as **data**, produce a summary of entities, their attributes, and relationships.

### 7. Domain Grouping
Group requirements into domains based on directory structure or topic similarity. Each domain gets a markdown summary with: overview, list of features, cross-references to other domains, requirement count.

### 8. Dependencies
Identify dependencies between requirements across files. Include IMPLICIT dependencies: cases where implementing feature A requires data or state from feature B, even if there is no explicit text reference.

### 9. Ambiguity Detection
Report:
- **underspecified**: behavior described but details missing
- **contradictory**: two files describe the same thing differently
- **missing_reference**: one file references a behavior/template/entity in another file that doesn't exist
- **implicit_assumption**: behavior depends on an undeclared dependency

### 10. Execution Hints
Files classified as **execution** → store as optional execution_hints (suggested change boundaries, dependency ordering).

## CRITICAL: Output Size Limit

Your ENTIRE JSON response MUST fit in a SINGLE message — you will NOT get a second turn.
Strict limits:
- MAX 50 requirements total. If your initial count exceeds 50, merge aggressively:
  group related CRUD operations, combine similar UI behaviors, roll detailed sub-features into parent features.
- Requirement briefs: ONE short sentence only
- Domain summaries: 1-2 sentences max
- MAX 10 ambiguities (only critical ones that block implementation)
- MAX 30 dependencies (only hard functional dependencies, skip informational references)
- Omit execution_hints entirely (use empty object: {})
- Do NOT split your response across messages. Everything in ONE JSON block.

## Output Format

Respond with valid JSON only (no markdown fences, no commentary):

{
  "file_classifications": {
    "path/to/file.md": "convention|feature|data|execution"
  },
  "conventions": {
    "categories": [
      {
        "name": "Category Name",
        "rules": ["Rule 1", "Rule 2"]
      }
    ]
  },
  "data_definitions": "Markdown string summarizing entities, catalogs, and data models",
  "requirements": [
    {
      "id": "REQ-DOMAIN-NNN",
      "title": "Short title",
      "source": "path/to/file.md",
      "source_section": "Section heading",
      "domain": "domain-name",
      "brief": "1-2 sentence description of the testable behavior",
      "acceptance_criteria": ["Concrete verifiable condition 1", "Condition 2"]
    }
  ],
  "domains": [
    {
      "name": "domain-name",
      "summary": "Markdown overview of the domain"
    }
  ],
  "dependencies": [
    {
      "from": "REQ-XXX-NNN",
      "to": "REQ-YYY-NNN",
      "type": "depends_on|references"
    }
  ],
  "ambiguities": [
    {
      "id": "AMB-NNN",
      "type": "underspecified|contradictory|missing_reference|implicit_assumption",
      "source": "path/to/file.md",
      "section": "Section heading",
      "description": "What is unclear or conflicting",
      "affects_requirements": ["REQ-XXX-NNN"]
    }
  ],
  "execution_hints": {}
}"""
