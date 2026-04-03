"""BDD test traceability — scenario extraction, test plan parsing, coverage tracking.

Provides the data models and parsers for the spec-to-test chain:
  Spec Scenario (WHEN/THEN) → Test Plan → Test Result → Coverage
"""

from __future__ import annotations

import logging
import re
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)


# ─── Digest Scenario Extraction ──────────────────────────────────


@dataclass
class DigestScenario:
    """A BDD scenario extracted from a spec's #### Scenario: block."""

    name: str
    when: str
    then: str
    slug: str

    def to_dict(self) -> dict:
        return asdict(self)

    @classmethod
    def from_dict(cls, d: dict) -> DigestScenario:
        return cls(
            name=d.get("name", ""),
            when=d.get("when", ""),
            then=d.get("then", ""),
            slug=d.get("slug", ""),
        )


def _slugify(text: str) -> str:
    """Convert text to kebab-case slug."""
    slug = text.lower().strip()
    slug = re.sub(r"[^a-z0-9\s-]", "", slug)
    slug = re.sub(r"[\s_]+", "-", slug)
    slug = re.sub(r"-+", "-", slug).strip("-")
    return slug


def parse_scenarios(section_text: str) -> list[DigestScenario]:
    """Parse #### Scenario: blocks from a requirement's markdown section.

    Extracts WHEN/THEN lines into structured DigestScenario objects.
    Returns empty list if no scenarios found or text lacks WHEN/THEN format.
    """
    scenarios: list[DigestScenario] = []
    seen_slugs: dict[str, int] = {}

    # Split on #### Scenario: headers
    parts = re.split(r"####\s+Scenario:\s*", section_text)
    if len(parts) <= 1:
        return []

    for part in parts[1:]:  # skip text before first scenario
        lines = part.strip().split("\n")
        if not lines:
            continue

        name = lines[0].strip()
        when_parts: list[str] = []
        then_parts: list[str] = []
        current: list[str] | None = None

        for line in lines[1:]:
            stripped = line.strip().lstrip("- ")
            # Stop at next section header
            if stripped.startswith("###"):
                break

            if stripped.startswith("**WHEN**") or stripped.startswith("WHEN "):
                text = re.sub(r"^\*\*WHEN\*\*\s*", "", stripped)
                text = re.sub(r"^WHEN\s+", "", text)
                when_parts.append(text)
                current = when_parts
            elif stripped.startswith("**THEN**") or stripped.startswith("THEN "):
                text = re.sub(r"^\*\*THEN\*\*\s*", "", stripped)
                text = re.sub(r"^THEN\s+", "", text)
                then_parts.append(text)
                current = then_parts
            elif stripped.startswith("**AND**") or stripped.startswith("AND "):
                text = re.sub(r"^\*\*AND\*\*\s*", "", stripped)
                text = re.sub(r"^AND\s+", "", text)
                if current is not None:
                    current.append(text)

        if not when_parts and not then_parts:
            continue

        # Generate unique slug
        slug = _slugify(name)
        if slug in seen_slugs:
            seen_slugs[slug] += 1
            slug = f"{slug}-{seen_slugs[slug]}"
        else:
            seen_slugs[slug] = 1

        scenarios.append(DigestScenario(
            name=name,
            when="; ".join(when_parts),
            then="; ".join(then_parts),
            slug=slug,
        ))

    return scenarios


# ─── Test Plan Parsing ───────────────────────────────────────────


@dataclass
class TestCase:
    """A test case from JOURNEY-TEST-PLAN.md."""

    scenario_slug: str
    req_id: str
    risk: str  # "HIGH" | "MEDIUM" | "LOW"
    test_file: str
    test_name: str
    category: str  # "happy" | "negative" | "boundary"
    result: str | None = None  # "pass" | "fail" | None

    def to_dict(self) -> dict:
        return asdict(self)

    @classmethod
    def from_dict(cls, d: dict) -> TestCase:
        return cls(**{k: v for k, v in d.items() if k in {f.name for f in cls.__dataclass_fields__.values()}})


@dataclass
class TestCoverage:
    """Aggregated test coverage data stored in state.extras."""

    plan_file: str = ""
    test_cases: list[TestCase] = field(default_factory=list)
    covered_reqs: list[str] = field(default_factory=list)
    uncovered_reqs: list[str] = field(default_factory=list)
    non_testable_reqs: list[str] = field(default_factory=list)
    total_tests: int = 0
    passed: int = 0
    failed: int = 0
    coverage_pct: float = 0.0
    parsed_at: str = ""

    def to_dict(self) -> dict:
        d = asdict(self)
        d["test_cases"] = [tc.to_dict() for tc in self.test_cases]
        return d

    @classmethod
    def from_dict(cls, d: dict) -> TestCoverage:
        cases = [TestCase.from_dict(tc) for tc in d.get("test_cases", [])]
        return cls(
            plan_file=d.get("plan_file", ""),
            test_cases=cases,
            covered_reqs=d.get("covered_reqs", []),
            uncovered_reqs=d.get("uncovered_reqs", []),
            non_testable_reqs=d.get("non_testable_reqs", []),
            total_tests=d.get("total_tests", 0),
            passed=d.get("passed", 0),
            failed=d.get("failed", 0),
            coverage_pct=d.get("coverage_pct", 0.0),
            parsed_at=d.get("parsed_at", ""),
        )


# Format A: strict — ## REQ-XXX: Title [HIGH]
_REQ_HEADER_RE = re.compile(
    r"^##\s+(REQ-[A-Z0-9_-]+):\s*(.+?)\s*\[(HIGH|MEDIUM|LOW|NON[_-]?TESTABLE)\]\s*$",
    re.IGNORECASE,
)
# Format B: journey-style — ## Journey N: Title (RISK risk)
_JOURNEY_HEADER_RE = re.compile(
    r"^##\s+(?:Journey\s+\d+:\s*)?(.+?)\s*\((HIGH|MEDIUM|LOW|NON[_-]?TESTABLE)\s*(?:risk)?\)\s*$",
    re.IGNORECASE,
)
_CHECKBOX_RE = re.compile(r"^-\s*\[([ xX])\]\s*(.*)")
_TEST_REF_RE = re.compile(r"^→\s*([^:]+\.(?:spec|test)\.\w+):\s*[\"'](.+?)[\"']")
_FILE_REF_RE = re.compile(r"\*\*File:\*\*\s*`([^`]+\.(?:spec|test)\.\w+)`")
_CATEGORY_RE = re.compile(r"^(Happy|Negative|Boundary|Edge)\b", re.IGNORECASE)
_RISK_INLINE_RE = re.compile(r"\b(HIGH|MEDIUM|LOW)\b", re.IGNORECASE)


def parse_test_plan(plan_path: Path) -> tuple[list[TestCase], list[str]]:
    """Parse JOURNEY-TEST-PLAN.md into test cases and non-testable REQ IDs.

    Supports two formats:
    - Format A (strict): ## REQ-XXX: Title [HIGH] + - [x] checkboxes
    - Format B (journey): ## Journey N: Title (LOW risk) + **File:** `name.spec.ts`
      + ### Scenario: lines with GIVEN/WHEN/THEN

    Returns (test_cases, non_testable_req_ids).
    """
    if not plan_path.is_file():
        logger.warning("Test plan not found: %s", plan_path)
        return [], []

    try:
        content = plan_path.read_text(encoding="utf-8")
    except OSError as e:
        logger.warning("Failed to read test plan: %s", e)
        return [], []

    test_cases: list[TestCase] = []
    non_testable: list[str] = []

    current_id: str = ""
    current_risk: str = ""
    current_file: str = ""
    current_case: dict[str, Any] | None = None
    scenario_count: int = 0

    for line in content.split("\n"):
        stripped = line.strip()

        # Format A: ## REQ-XXX: Title [HIGH]
        m = _REQ_HEADER_RE.match(stripped)
        if m:
            if current_case:
                test_cases.append(_build_test_case(current_case, current_id, current_risk))
                current_case = None
            # Flush journey-based entry
            if current_id and current_file and scenario_count > 0 and not any(
                tc.req_id == current_id for tc in test_cases
            ):
                test_cases.append(_build_test_case(
                    {"slug": _slugify(current_id), "category": "happy",
                     "test_file": current_file, "test_name": current_id},
                    current_id, current_risk,
                ))

            current_id = m.group(1)
            risk_raw = m.group(3).upper().replace("-", "_")
            if "NON" in risk_raw and "TESTABLE" in risk_raw:
                non_testable.append(current_id)
                current_id = ""
                current_risk = ""
            else:
                current_risk = risk_raw
            current_file = ""
            scenario_count = 0
            continue

        # Format B: ## Journey N: Title (LOW risk)
        jm = _JOURNEY_HEADER_RE.match(stripped)
        if jm:
            # Flush previous journey entry
            if current_case:
                test_cases.append(_build_test_case(current_case, current_id, current_risk))
                current_case = None
            if current_id and current_file and scenario_count > 0 and not any(
                tc.req_id == current_id for tc in test_cases
            ):
                test_cases.append(_build_test_case(
                    {"slug": _slugify(current_id), "category": "happy",
                     "test_file": current_file, "test_name": current_id},
                    current_id, current_risk,
                ))

            title = jm.group(1).strip()
            current_id = _slugify(title) or title
            risk_raw = jm.group(2).upper()
            if "NON" in risk_raw and "TESTABLE" in risk_raw:
                non_testable.append(current_id)
                current_id = ""
                current_risk = ""
            else:
                current_risk = risk_raw
            current_file = ""
            scenario_count = 0
            continue

        if not current_id:
            continue

        # **File:** `journey-xxx.spec.ts`
        fm = _FILE_REF_RE.search(stripped)
        if fm:
            current_file = fm.group(1).strip()
            continue

        # ### Scenario: lines (format B)
        if stripped.startswith("### Scenario:"):
            scenario_count += 1
            scenario_name = stripped.replace("### Scenario:", "").strip()
            # Each scenario = one test case for the journey
            if current_file:
                test_cases.append(_build_test_case(
                    {"slug": _slugify(scenario_name), "category": "happy",
                     "test_file": current_file, "test_name": scenario_name},
                    current_id, current_risk,
                ))
            continue

        # Format A: checkbox lines
        cm = _CHECKBOX_RE.match(stripped)
        if cm:
            if current_case:
                test_cases.append(_build_test_case(current_case, current_id, current_risk))

            text = cm.group(2).strip()
            cat_m = _CATEGORY_RE.match(text)
            category = cat_m.group(1).lower() if cat_m else "happy"
            slug = _slugify(text[:60])

            current_case = {
                "slug": slug,
                "category": category,
                "text": text,
                "test_file": current_file,
                "test_name": "",
            }
            continue

        # → file.spec.ts: "test name"
        tm = _TEST_REF_RE.match(stripped)
        if tm and current_case:
            current_case["test_file"] = tm.group(1).strip()
            current_case["test_name"] = tm.group(2).strip()
            continue

    # Flush last entries
    if current_case and current_id:
        test_cases.append(_build_test_case(current_case, current_id, current_risk))
    elif current_id and current_file and scenario_count > 0 and not any(
        tc.req_id == current_id for tc in test_cases
    ):
        test_cases.append(_build_test_case(
            {"slug": _slugify(current_id), "category": "happy",
             "test_file": current_file, "test_name": current_id},
            current_id, current_risk,
        ))

    return test_cases, non_testable


def _build_test_case(case: dict, req_id: str, risk: str) -> TestCase:
    return TestCase(
        scenario_slug=case["slug"],
        req_id=req_id,
        risk=risk,
        test_file=case.get("test_file", ""),
        test_name=case.get("test_name", ""),
        category=case.get("category", "happy"),
    )


# ─── Coverage Calculation ────────────────────────────────────────


def build_test_coverage(
    test_cases: list[TestCase],
    non_testable: list[str],
    test_results: dict[tuple[str, str], str],
    digest_req_ids: list[str],
    plan_file: str = "",
) -> TestCoverage:
    """Build TestCoverage by cross-referencing plan, results, and digest.

    Args:
        test_cases: Parsed from JOURNEY-TEST-PLAN.md
        non_testable: REQ IDs marked non-testable
        test_results: {(file, name): "pass"|"fail"} from profile.parse_test_results()
        digest_req_ids: All REQ IDs from the digest
        plan_file: Path to the plan file
    """
    from datetime import datetime, timezone

    # Match test results to test cases
    for tc in test_cases:
        if tc.test_file and tc.test_name:
            key = (tc.test_file.lower().strip(), tc.test_name.lower().strip())
            # Try exact match first, then fuzzy
            result = test_results.get(key)
            if result is None:
                for (f, n), r in test_results.items():
                    if f.lower().strip() == key[0] and _fuzzy_match(n, tc.test_name):
                        result = r
                        break
            tc.result = result

    # Compute coverage
    reqs_with_tests = {tc.req_id for tc in test_cases if tc.test_file}
    non_testable_set = set(non_testable)
    testable_reqs = [r for r in digest_req_ids if r not in non_testable_set]

    covered = [r for r in testable_reqs if r in reqs_with_tests]
    uncovered = [r for r in testable_reqs if r not in reqs_with_tests]

    passed = sum(1 for tc in test_cases if tc.result == "pass")
    failed = sum(1 for tc in test_cases if tc.result == "fail")

    total_testable = len(covered) + len(uncovered)
    coverage_pct = (len(covered) / total_testable * 100) if total_testable > 0 else 0.0

    return TestCoverage(
        plan_file=plan_file,
        test_cases=test_cases,
        covered_reqs=covered,
        uncovered_reqs=uncovered,
        non_testable_reqs=list(non_testable),
        total_tests=len(test_cases),
        passed=passed,
        failed=failed,
        coverage_pct=round(coverage_pct, 1),
        parsed_at=datetime.now(timezone.utc).isoformat(),
    )


def _fuzzy_match(a: str, b: str) -> bool:
    """Case-insensitive, whitespace-tolerant match."""
    return re.sub(r"\s+", " ", a.lower().strip()) == re.sub(r"\s+", " ", b.lower().strip())
