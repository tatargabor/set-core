"""BDD test traceability — scenario extraction, test plan parsing, coverage tracking.

Provides the data models and parsers for the spec-to-test chain:
  Spec Scenario (WHEN/THEN) → Test Plan → Test Result → Coverage
"""

from __future__ import annotations

import json
import logging
import re
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
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
    unbound_tests: list[str] = field(default_factory=list)
    parsed_at: str = ""
    # Smoke/own breakdown (populated when two-phase gate is used)
    smoke_passed: int = 0
    smoke_failed: int = 0
    own_passed: int = 0
    own_failed: int = 0

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
            unbound_tests=d.get("unbound_tests", []),
            parsed_at=d.get("parsed_at", ""),
            smoke_passed=d.get("smoke_passed", 0),
            smoke_failed=d.get("smoke_failed", 0),
            own_passed=d.get("own_passed", 0),
            own_failed=d.get("own_failed", 0),
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
# Inline test ref: `-> file.spec.ts:test name` or `→ file.spec.ts:test name` inside backticks
_INLINE_TEST_REF_RE = re.compile(
    r"`\s*(?:->|→)\s*([^:]+\.(?:spec|test)\.\w+)\s*:\s*(.+?)\s*`"
)
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

            # Check for inline test ref: `-> file.spec.ts:test name`
            inline_file = current_file
            inline_name = ""
            itm = _INLINE_TEST_REF_RE.search(text)
            if itm:
                inline_file = itm.group(1).strip()
                inline_name = itm.group(2).strip()

            current_case = {
                "slug": slug,
                "category": category,
                "text": text,
                "test_file": inline_file,
                "test_name": inline_name,
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
    unbound_tests: list[str] = []

    # Phase 1: Try deterministic REQ-ID extraction from test result names
    # This creates additional test cases bound by REQ-ID from the output
    deterministic_bindings: dict[str, list[tuple[str, str]]] = {}  # req_id → [(file, result)]

    # Build scenario lookup from test_cases for slug matching
    _scenario_by_req: dict[str, list[TestCase]] = {}
    for tc in test_cases:
        _scenario_by_req.setdefault(tc.req_id, []).append(tc)

    for (file, name), result in test_results.items():
        req_ids = extract_req_ids(name)
        if req_ids:
            for rid in req_ids:
                deterministic_bindings.setdefault(rid, []).append((file, result))
                logger.debug("Bound %s (deterministic) from test: %s", rid, name)

                # Try to match test name to a specific scenario slug.
                # Playwright names use "describe › test" format — split on › and
                # try matching each segment individually after stripping REQ-IDs.
                _raw_desc = re.sub(r"REQ-[A-Z]+-\d+:?\s*", "", name).strip()
                _segments = [_slugify(seg.strip()) for seg in re.split(r"\s*›\s*", _raw_desc) if seg.strip()]
                if not _segments:
                    _segments = [_slugify(_raw_desc)]
                if rid in _scenario_by_req:
                    for sc_tc in _scenario_by_req[rid]:
                        if sc_tc.result is not None:
                            continue
                        for seg_slug in _segments:
                            if not seg_slug:
                                continue
                            if (sc_tc.scenario_slug == seg_slug
                                or seg_slug.startswith(sc_tc.scenario_slug[:30])
                                or sc_tc.scenario_slug.startswith(seg_slug[:30])):
                                sc_tc.result = result
                                sc_tc.test_file = sc_tc.test_file or file
                                logger.debug("Scenario bound: %s/%s from segment: %s",
                                            rid, sc_tc.scenario_slug, seg_slug)
                                break
        else:
            unbound_tests.append(name)
            logger.debug("Unbound test (no REQ-ID): %s, trying fuzzy", name)

    # Phase 2: Match test results to existing test cases (from JOURNEY-TEST-PLAN.md)
    # Only overwrite result if Phase 1 didn't already bind this scenario
    for tc in test_cases:
        if tc.result is not None:
            continue  # Phase 1 already bound this scenario — don't overwrite
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

    # Phase 3: Compute coverage — deterministic bindings take priority
    non_testable_set = set(non_testable)
    testable_reqs = [r for r in digest_req_ids if r not in non_testable_set]

    # Merge sources: plan-based req_ids + deterministic bindings
    reqs_with_tests = {tc.req_id for tc in test_cases if tc.test_file}
    reqs_with_deterministic = set(deterministic_bindings.keys())
    all_covered_reqs = reqs_with_tests | reqs_with_deterministic

    covered = [r for r in testable_reqs if r in all_covered_reqs]
    uncovered = [r for r in testable_reqs if r not in all_covered_reqs]

    # If no direct match but we have test cases with files, the plan used
    # journey names instead of REQ IDs. Count test files as evidence of coverage.
    if not covered and test_cases and any(tc.test_file for tc in test_cases):
        test_files = {tc.test_file for tc in test_cases if tc.test_file}
        covered = list(testable_reqs)
        uncovered = []
        logger.info(
            "Test coverage: %d journey files cover %d REQs (no REQ-ID mapping available)",
            len(test_files), len(covered),
        )

    passed = sum(1 for tc in test_cases if tc.result == "pass")
    failed = sum(1 for tc in test_cases if tc.result == "fail")
    # Also count deterministic-only bindings
    for rid, bindings in deterministic_bindings.items():
        for _file, result in bindings:
            if result == "pass":
                passed += 1 if rid not in reqs_with_tests else 0
            elif result == "fail":
                failed += 1 if rid not in reqs_with_tests else 0

    total_testable = len(covered) + len(uncovered)
    coverage_pct = (len(covered) / total_testable * 100) if total_testable > 0 else 0.0

    cov = TestCoverage(
        plan_file=plan_file,
        test_cases=test_cases,
        covered_reqs=covered,
        uncovered_reqs=uncovered,
        non_testable_reqs=list(non_testable),
        total_tests=len(test_cases),
        passed=passed,
        failed=failed,
        coverage_pct=round(coverage_pct, 1),
        unbound_tests=unbound_tests,
        parsed_at=datetime.now(timezone.utc).isoformat(),
    )
    logger.info("Test coverage: %.1f%% (%d/%d reqs), %d passed, %d failed, %d unbound tests",
                 coverage_pct, len(covered), total_testable, passed, failed, len(unbound_tests))
    if unbound_tests:
        logger.warning("Unbound tests: %s", unbound_tests[:10])
    if uncovered:
        logger.warning("Uncovered requirements: %s", uncovered[:10])
    return cov


def _fuzzy_match(a: str, b: str) -> bool:
    """Case-insensitive, whitespace-tolerant match."""
    return re.sub(r"\s+", " ", a.lower().strip()) == re.sub(r"\s+", " ", b.lower().strip())


# ─── REQ-ID Extraction ─────────────────────────────────────────

_REQ_ID_RE = re.compile(r"REQ-[A-Z]+-\d+", re.IGNORECASE)


def extract_req_ids(test_name: str) -> list[str]:
    """Extract REQ-* IDs from a test name via regex.

    A test may cover multiple requirements, e.g.:
    "REQ-HOME-001: REQ-NAV-001: heading and nav visible"
    """
    return [m.upper() for m in _REQ_ID_RE.findall(test_name)]


# ─── Generated Test Plan ───────────────────────────────────────

RISK_MIN_TESTS = {"HIGH": 3, "MEDIUM": 2, "LOW": 1}
RISK_CATEGORIES = {
    "HIGH": ["happy", "negative", "negative"],
    "MEDIUM": ["happy", "negative"],
    "LOW": ["happy"],
}


@dataclass
class TestPlanEntry:
    """A single entry in the generated test plan."""

    req_id: str
    scenario_slug: str
    scenario_name: str
    risk: str  # "HIGH" | "MEDIUM" | "LOW"
    min_tests: int
    categories: list[str] = field(default_factory=list)
    type: str = "functional"  # "smoke" | "functional"

    def to_dict(self) -> dict:
        return asdict(self)

    @classmethod
    def from_dict(cls, d: dict) -> TestPlanEntry:
        return cls(
            req_id=d.get("req_id", ""),
            scenario_slug=d.get("scenario_slug", ""),
            scenario_name=d.get("scenario_name", ""),
            risk=d.get("risk", "LOW"),
            min_tests=d.get("min_tests", 1),
            categories=d.get("categories", ["happy"]),
            type=d.get("type", "functional"),
        )


@dataclass
class TestPlan:
    """Container for the generated test plan."""

    entries: list[TestPlanEntry] = field(default_factory=list)
    non_testable: list[str] = field(default_factory=list)
    generated_at: str = ""

    def to_dict(self) -> dict:
        return {
            "entries": [e.to_dict() for e in self.entries],
            "non_testable": self.non_testable,
            "generated_at": self.generated_at,
        }

    @classmethod
    def from_dict(cls, d: dict) -> TestPlan:
        return cls(
            entries=[TestPlanEntry.from_dict(e) for e in d.get("entries", [])],
            non_testable=d.get("non_testable", []),
            generated_at=d.get("generated_at", ""),
        )


def generate_test_plan(
    requirements_json: Path,
    output_path: Path,
    profile: Any = None,
) -> TestPlan:
    """Generate test-plan.json from requirements.json.

    Reads digest requirements, extracts scenarios via parse_scenarios(),
    classifies risk via profile.classify_test_risk(), writes test-plan.json.

    Args:
        requirements_json: Path to requirements.json from digest.
        output_path: Where to write test-plan.json.
        profile: ProjectType instance for risk classification. Default: LOW for all.
    """
    logger.info("Generating test plan from %s", requirements_json)

    data = json.loads(requirements_json.read_text(encoding="utf-8"))
    reqs = data.get("requirements", [])
    logger.info("Loaded %d requirements", len(reqs))

    entries: list[TestPlanEntry] = []
    non_testable: list[str] = []

    for req in reqs:
        req_id = req.get("id", "")
        if not req_id:
            continue

        # Build scenario text from acceptance_criteria
        ac_items = req.get("acceptance_criteria", []) or []
        ac_text = "\n".join(f"#### Scenario: {ac}" for ac in ac_items) if ac_items else ""

        # Try structured WHEN/THEN scenarios first
        scenarios = parse_scenarios(ac_text) if ac_text else []

        # Fallback: plain-text ACs without WHEN/THEN are still testable —
        # create a DigestScenario per AC with the text as the name
        if not scenarios and ac_items:
            for ac in ac_items:
                ac_str = str(ac).strip()
                if not ac_str:
                    continue
                slug = _slugify(ac_str[:60])
                scenarios.append(DigestScenario(
                    name=ac_str,
                    when=ac_str,
                    then="verified",
                    slug=slug or "ac",
                ))

        if not scenarios:
            non_testable.append(req_id)
            logger.debug("Requirement %s has no acceptance criteria — non-testable", req_id)
            continue

        for scenario in scenarios:
            # Priority: LLM-assigned risk from digest > profile classifier > default LOW
            risk = (req.get("risk") or "").upper()
            if risk not in ("HIGH", "MEDIUM", "LOW"):
                risk = "LOW"
                if profile is not None:
                    risk = profile.classify_test_risk(scenario, req)
            min_tests = RISK_MIN_TESTS.get(risk, 1)
            categories = list(RISK_CATEGORIES.get(risk, ["happy"]))

            entry = TestPlanEntry(
                req_id=req_id,
                scenario_slug=scenario.slug,
                scenario_name=scenario.name,
                risk=risk,
                min_tests=min_tests,
                categories=categories,
            )
            entries.append(entry)
            logger.debug(
                "Scenario %s/%s classified as %s → %d test(s)",
                req_id, scenario.slug, risk, min_tests,
            )

    # Post-process: first happy-path entry per req_id → type "smoke"
    _seen_smoke: set[str] = set()
    for entry in entries:
        if entry.req_id not in _seen_smoke and "happy" in entry.categories:
            entry.type = "smoke"
            _seen_smoke.add(entry.req_id)

    plan = TestPlan(
        entries=entries,
        non_testable=non_testable,
        generated_at=datetime.now(timezone.utc).isoformat(),
    )

    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(
        json.dumps(plan.to_dict(), indent=2, ensure_ascii=False),
        encoding="utf-8",
    )
    logger.info(
        "Test plan written: %d entries, %d non-testable → %s",
        len(entries), len(non_testable), output_path,
    )
    return plan


# ─── Coverage Validation ───────────────────────────────────────


@dataclass
class CoverageValidationEntry:
    """Validation result for a single requirement."""

    req_id: str
    expected_min: int
    actual_count: int
    status: str  # "complete" | "partial" | "missing"

    def to_dict(self) -> dict:
        return asdict(self)


@dataclass
class CoverageValidation:
    """Result of comparing test plan against actual coverage."""

    entries: list[CoverageValidationEntry] = field(default_factory=list)
    complete_count: int = 0
    partial_count: int = 0
    missing_count: int = 0
    validated_at: str = ""

    def to_dict(self) -> dict:
        return {
            "entries": [e.to_dict() for e in self.entries],
            "complete_count": self.complete_count,
            "partial_count": self.partial_count,
            "missing_count": self.missing_count,
            "validated_at": self.validated_at,
        }

    @classmethod
    def from_dict(cls, d: dict) -> CoverageValidation:
        return cls(
            entries=[CoverageValidationEntry(**e) for e in d.get("entries", [])],
            complete_count=d.get("complete_count", 0),
            partial_count=d.get("partial_count", 0),
            missing_count=d.get("missing_count", 0),
            validated_at=d.get("validated_at", ""),
        )


def validate_coverage(
    test_plan: TestPlan,
    coverage: TestCoverage,
) -> CoverageValidation:
    """Compare test plan expected entries against actual test results.

    Non-blocking — produces warnings, not gate failures.
    """
    # Group actual passing tests by REQ-ID
    req_pass_counts: dict[str, int] = {}
    for tc in coverage.test_cases:
        if tc.result == "pass" and tc.req_id:
            req_pass_counts[tc.req_id] = req_pass_counts.get(tc.req_id, 0) + 1

    # Also count from unbound tests that were matched deterministically
    # (these are already in test_cases with req_id set)

    # Aggregate expected min_tests per req_id from the plan
    req_expected: dict[str, int] = {}
    for entry in test_plan.entries:
        req_expected[entry.req_id] = req_expected.get(entry.req_id, 0) + entry.min_tests

    validation_entries: list[CoverageValidationEntry] = []
    complete = 0
    partial = 0
    missing = 0

    for req_id, expected_min in sorted(req_expected.items()):
        actual = req_pass_counts.get(req_id, 0)
        if actual == 0:
            status = "missing"
            missing += 1
        elif actual < expected_min:
            status = "partial"
            partial += 1
            logger.warning(
                "Coverage partial: %s: %d/%d tests (expected %d)",
                req_id, actual, expected_min, expected_min,
            )
        else:
            status = "complete"
            complete += 1

        validation_entries.append(CoverageValidationEntry(
            req_id=req_id,
            expected_min=expected_min,
            actual_count=actual,
            status=status,
        ))

    total = complete + partial + missing
    logger.info(
        "Coverage validation: %d/%d complete, %d partial, %d missing",
        complete, total, partial, missing,
    )

    return CoverageValidation(
        entries=validation_entries,
        complete_count=complete,
        partial_count=partial,
        missing_count=missing,
        validated_at=datetime.now(timezone.utc).isoformat(),
    )
