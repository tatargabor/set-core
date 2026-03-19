"""Tests for set_orch.digest — scanning, ID stabilization, validation, coverage, freshness."""

import json
import os
import shutil
import sys
import tempfile

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", "lib"))

from set_orch.digest import (
    ScanResult,
    DigestResult,
    scan_spec_directory,
    validate_digest,
    stabilize_ids,
    check_digest_freshness,
    populate_coverage,
    check_coverage_gaps,
    check_coverage_gaps_internal,
    update_coverage_status,
    parse_digest_response,
    generate_triage_md,
    parse_triage_md,
    merge_triage_to_ambiguities,
    merge_planner_resolutions,
    build_digest_prompt,
)


@pytest.fixture
def tmp_dir():
    d = tempfile.mkdtemp()
    yield d
    shutil.rmtree(d, ignore_errors=True)


@pytest.fixture
def spec_dir(tmp_dir):
    """Create a mock spec directory with multiple files."""
    spec = os.path.join(tmp_dir, "specs")
    os.makedirs(spec)
    with open(os.path.join(spec, "README.md"), "w") as f:
        f.write("# Project Spec\n\nOverview of the project.")
    with open(os.path.join(spec, "features.md"), "w") as f:
        f.write("# Features\n\n- Feature A\n- Feature B")
    with open(os.path.join(spec, "data.yaml"), "w") as f:
        f.write("entities:\n  - name: User\n  - name: Product")
    # Archive dir should be ignored
    os.makedirs(os.path.join(spec, "archive"))
    with open(os.path.join(spec, "archive", "old.md"), "w") as f:
        f.write("old stuff")
    return spec


@pytest.fixture
def digest_dir(tmp_dir):
    """Create a mock digest directory."""
    d = os.path.join(tmp_dir, "digest")
    os.makedirs(d)
    return d


# ─── scan_spec_directory ──────────────────────────────────────────


class TestScanSpecDirectory:
    def test_scan_directory(self, spec_dir):
        result = scan_spec_directory(spec_dir)
        assert result.file_count == 3  # README.md, features.md, data.yaml
        assert result.master_file == "README.md"
        assert result.source_hash != ""
        assert "features.md" in result.files

    def test_scan_ignores_archive(self, spec_dir):
        result = scan_spec_directory(spec_dir)
        for f in result.files:
            assert "archive" not in f

    def test_scan_single_file(self, spec_dir):
        single = os.path.join(spec_dir, "features.md")
        result = scan_spec_directory(single)
        assert result.file_count == 1
        assert result.files == ["features.md"]

    def test_scan_nonexistent(self):
        with pytest.raises(FileNotFoundError):
            scan_spec_directory("/nonexistent/path")

    def test_scan_empty_dir(self, tmp_dir):
        empty = os.path.join(tmp_dir, "empty")
        os.makedirs(empty)
        with pytest.raises(FileNotFoundError, match="No spec files"):
            scan_spec_directory(empty)

    def test_deterministic_hash(self, spec_dir):
        r1 = scan_spec_directory(spec_dir)
        r2 = scan_spec_directory(spec_dir)
        assert r1.source_hash == r2.source_hash


# ─── validate_digest ──────────────────────────────────────────────


class TestValidateDigest:
    def test_valid_digest(self):
        digest = DigestResult(
            requirements=[
                {"id": "REQ-CART-001", "domain": "cart", "title": "Add to cart",
                 "acceptance_criteria": ["POST /api/cart → 201"]},
            ],
            conventions={"categories": [{"name": "UI", "rules": ["rule1"]}]},
            domains=[{"name": "cart", "summary": "Cart domain"}],
            dependencies=[],
        )
        errors = validate_digest(digest)
        assert errors == []

    def test_invalid_id_format(self):
        digest = DigestResult(
            requirements=[{"id": "bad-id", "domain": "x"}],
            conventions={"categories": []},
            domains=[{"name": "x"}],
        )
        errors = validate_digest(digest)
        assert any("Invalid requirement ID" in e for e in errors)

    def test_duplicate_ids(self):
        digest = DigestResult(
            requirements=[
                {"id": "REQ-A-001", "domain": "a"},
                {"id": "REQ-A-001", "domain": "a"},
            ],
            conventions={"categories": []},
            domains=[{"name": "a"}],
        )
        errors = validate_digest(digest)
        assert any("Duplicate" in e for e in errors)

    def test_missing_domain_summary(self):
        digest = DigestResult(
            requirements=[{"id": "REQ-X-001", "domain": "x"}],
            conventions={"categories": []},
            domains=[],  # no domain summary for 'x'
        )
        errors = validate_digest(digest)
        assert any("Domain 'x'" in e for e in errors)

    def test_invalid_dependency_ref(self):
        digest = DigestResult(
            requirements=[{"id": "REQ-A-001", "domain": "a"}],
            conventions={"categories": []},
            domains=[{"name": "a"}],
            dependencies=[{"from": "REQ-A-001", "to": "REQ-NONEXIST-999"}],
        )
        errors = validate_digest(digest)
        assert any("non-existent" in e for e in errors)

    def test_cross_cutting_missing_affects(self):
        digest = DigestResult(
            requirements=[
                {"id": "REQ-CC-001", "domain": "cc", "cross_cutting": True},
            ],
            conventions={"categories": []},
            domains=[{"name": "cc"}],
        )
        errors = validate_digest(digest)
        assert any("affects_domains" in e for e in errors)

    def test_acceptance_criteria_populated(self):
        """Requirements with acceptance_criteria pass validation."""
        digest = DigestResult(
            requirements=[
                {
                    "id": "REQ-CART-001",
                    "domain": "cart",
                    "title": "Add to cart",
                    "acceptance_criteria": [
                        "POST /api/cart/items → 201",
                        "Stock decremented by quantity",
                    ],
                },
            ],
            conventions={"categories": [{"name": "UI", "rules": ["rule1"]}]},
            domains=[{"name": "cart", "summary": "Cart domain"}],
        )
        errors = validate_digest(digest)
        assert errors == []

    def test_acceptance_criteria_empty_array(self):
        """Requirements with empty acceptance_criteria pass validation."""
        digest = DigestResult(
            requirements=[
                {
                    "id": "REQ-CART-001",
                    "domain": "cart",
                    "title": "Add to cart",
                    "acceptance_criteria": [],
                },
            ],
            conventions={"categories": [{"name": "UI", "rules": ["rule1"]}]},
            domains=[{"name": "cart", "summary": "Cart domain"}],
        )
        errors = validate_digest(digest)
        assert errors == []

    def test_acceptance_criteria_missing_warns(self):
        """Requirements without acceptance_criteria field produce a warning."""
        digest = DigestResult(
            requirements=[
                {"id": "REQ-CART-001", "domain": "cart", "title": "Add to cart"},
            ],
            conventions={"categories": [{"name": "UI", "rules": ["rule1"]}]},
            domains=[{"name": "cart", "summary": "Cart domain"}],
        )
        errors = validate_digest(digest)
        assert any("[WARN]" in e and "acceptance_criteria" in e for e in errors)


# ─── stabilize_ids ────────────────────────────────────────────────


class TestStabilizeIds:
    def test_preserves_existing_ids(self, digest_dir):
        # Create existing requirements
        old_reqs = {
            "requirements": [
                {"id": "REQ-A-001", "source": "a.md", "source_section": "Sec1"},
            ]
        }
        with open(os.path.join(digest_dir, "requirements.json"), "w") as f:
            json.dump(old_reqs, f)

        new_digest = DigestResult(
            requirements=[
                {"id": "REQ-A-999", "source": "a.md", "source_section": "Sec1"},
            ]
        )
        result = stabilize_ids(new_digest, digest_dir)
        assert result.requirements[0]["id"] == "REQ-A-001"

    def test_marks_removed(self, digest_dir):
        old_reqs = {
            "requirements": [
                {"id": "REQ-OLD-001", "source": "old.md", "source_section": "X"},
            ]
        }
        with open(os.path.join(digest_dir, "requirements.json"), "w") as f:
            json.dump(old_reqs, f)

        new_digest = DigestResult(
            requirements=[
                {"id": "REQ-NEW-001", "source": "new.md", "source_section": "Y"},
            ]
        )
        result = stabilize_ids(new_digest, digest_dir)
        ids = [r["id"] for r in result.requirements]
        assert "REQ-NEW-001" in ids
        removed = [r for r in result.requirements if r.get("status") == "removed"]
        assert len(removed) == 1
        assert removed[0]["id"] == "REQ-OLD-001"

    def test_no_existing_digest(self, digest_dir):
        new_digest = DigestResult(
            requirements=[{"id": "REQ-A-001", "source": "a.md"}]
        )
        result = stabilize_ids(new_digest, digest_dir)
        assert result.requirements == new_digest.requirements


# ─── check_digest_freshness ──────────────────────────────────────


class TestCheckDigestFreshness:
    def test_missing_digest(self, spec_dir, tmp_dir):
        result = check_digest_freshness(spec_dir, os.path.join(tmp_dir, "nodigest"))
        assert result == "missing"

    def test_fresh_digest(self, spec_dir, digest_dir):
        scan = scan_spec_directory(spec_dir)
        index = {"source_hash": scan.source_hash}
        with open(os.path.join(digest_dir, "index.json"), "w") as f:
            json.dump(index, f)
        result = check_digest_freshness(spec_dir, digest_dir)
        assert result == "fresh"

    def test_stale_digest(self, spec_dir, digest_dir):
        index = {"source_hash": "outdated-hash"}
        with open(os.path.join(digest_dir, "index.json"), "w") as f:
            json.dump(index, f)
        result = check_digest_freshness(spec_dir, digest_dir)
        assert result == "stale"


# ─── Coverage tracking ───────────────────────────────────────────


class TestCoverageTracking:
    def test_populate_coverage(self, digest_dir):
        # Create requirements
        reqs = {
            "requirements": [
                {"id": "REQ-A-001"},
                {"id": "REQ-A-002"},
                {"id": "REQ-B-001"},
            ]
        }
        with open(os.path.join(digest_dir, "requirements.json"), "w") as f:
            json.dump(reqs, f)

        plan = {
            "changes": [
                {"name": "change-a", "requirements": ["REQ-A-001", "REQ-A-002"]},
                {"name": "change-b", "requirements": ["REQ-B-001"]},
            ]
        }
        coverage = populate_coverage(plan, digest_dir)
        assert "REQ-A-001" in coverage
        assert coverage["REQ-A-001"]["change"] == "change-a"
        assert coverage["REQ-B-001"]["change"] == "change-b"

    def test_coverage_gaps(self, digest_dir):
        reqs = {
            "requirements": [
                {"id": "REQ-A-001"},
                {"id": "REQ-A-002"},
            ]
        }
        with open(os.path.join(digest_dir, "requirements.json"), "w") as f:
            json.dump(reqs, f)

        coverage = {"REQ-A-001": {"change": "c1", "status": "planned"}}
        gaps = check_coverage_gaps_internal(coverage, digest_dir)
        assert gaps == ["REQ-A-002"]

    def test_update_coverage_status(self, digest_dir):
        cov = {
            "coverage": {
                "REQ-A-001": {"change": "c1", "status": "planned"},
                "REQ-A-002": {"change": "c2", "status": "planned"},
            },
            "uncovered": [],
        }
        with open(os.path.join(digest_dir, "coverage.json"), "w") as f:
            json.dump(cov, f)

        update_coverage_status("c1", "merged", digest_dir)

        with open(os.path.join(digest_dir, "coverage.json")) as f:
            updated = json.load(f)
        assert updated["coverage"]["REQ-A-001"]["status"] == "merged"
        assert updated["coverage"]["REQ-A-002"]["status"] == "planned"

        # Check merged history was persisted
        history_path = os.path.join(digest_dir, "coverage-merged.json")
        assert os.path.isfile(history_path)
        with open(history_path) as f:
            history = json.load(f)
        assert "REQ-A-001" in history


# ─── parse_digest_response ───────────────────────────────────────


class TestParseDigestResponse:
    def test_direct_json(self):
        data = {"requirements": [{"id": "REQ-A-001"}], "domains": []}
        result = parse_digest_response(json.dumps(data))
        assert len(result.requirements) == 1

    def test_markdown_fenced(self):
        raw = '```json\n{"requirements": [{"id": "REQ-B-001"}], "domains": []}\n```'
        result = parse_digest_response(raw)
        assert len(result.requirements) == 1

    def test_with_preamble(self):
        raw = 'Here is the analysis:\n{"requirements": [{"id": "REQ-C-001"}], "domains": []}'
        result = parse_digest_response(raw)
        assert result.requirements[0]["id"] == "REQ-C-001"

    def test_invalid_json(self):
        with pytest.raises(ValueError):
            parse_digest_response("This is not JSON at all")


# ─── Triage pipeline ─────────────────────────────────────────────


class TestTriagePipeline:
    def test_generate_and_parse_triage(self, tmp_dir):
        ambiguities = [
            {
                "id": "AMB-001",
                "type": "underspecified",
                "source": "spec.md",
                "section": "Cart",
                "description": "Unclear coupon behavior",
            }
        ]
        output = os.path.join(tmp_dir, "triage.md")
        generate_triage_md(ambiguities, output)

        assert os.path.isfile(output)
        decisions = parse_triage_md(output)
        assert "AMB-001" in decisions
        assert decisions["AMB-001"]["decision"] == ""  # no decision yet

    def test_parse_with_decisions(self, tmp_dir):
        content = """# Ambiguity Triage

### AMB-001 [underspecified]
**Description:** Unclear
**Decision:** defer
**Note:** Will handle in sprint 2

---

### AMB-002 [contradictory]
**Description:** Conflict
**Decision:** fix
**Note:** Fix spec first

---
"""
        path = os.path.join(tmp_dir, "triage.md")
        with open(path, "w") as f:
            f.write(content)

        decisions = parse_triage_md(path)
        assert decisions["AMB-001"]["decision"] == "defer"
        assert decisions["AMB-002"]["decision"] == "fix"
        assert decisions["AMB-002"]["note"] == "Fix spec first"

    def test_parse_ignores_removed(self, tmp_dir):
        content = """### AMB-001 [REMOVED]
**Decision:** defer
**Note:** old

---
"""
        path = os.path.join(tmp_dir, "triage.md")
        with open(path, "w") as f:
            f.write(content)
        decisions = parse_triage_md(path)
        assert "AMB-001" not in decisions

    def test_merge_triage_to_ambiguities(self, tmp_dir):
        amb_data = {
            "ambiguities": [
                {"id": "AMB-001", "type": "underspecified"},
                {"id": "AMB-002", "type": "contradictory"},
            ]
        }
        amb_path = os.path.join(tmp_dir, "ambiguities.json")
        with open(amb_path, "w") as f:
            json.dump(amb_data, f)

        decisions = {
            "AMB-001": {"decision": "defer", "note": "later"},
        }
        merge_triage_to_ambiguities(amb_path, decisions)

        with open(amb_path) as f:
            result = json.load(f)
        assert result["ambiguities"][0]["resolution"] == "deferred"
        assert result["ambiguities"][0]["resolved_by"] == "triage"
        assert "resolution" not in result["ambiguities"][1]

    def test_merge_planner_resolutions(self, tmp_dir):
        amb_data = {
            "ambiguities": [
                {"id": "AMB-001", "type": "underspecified"},
            ]
        }
        amb_path = os.path.join(tmp_dir, "ambiguities.json")
        with open(amb_path, "w") as f:
            json.dump(amb_data, f)

        plan_data = {
            "changes": [
                {
                    "name": "c1",
                    "resolved_ambiguities": [
                        {"id": "AMB-001", "resolution_note": "Resolved in c1"},
                    ],
                },
            ]
        }
        plan_path = os.path.join(tmp_dir, "plan.json")
        with open(plan_path, "w") as f:
            json.dump(plan_data, f)

        merge_planner_resolutions(amb_path, plan_path)

        with open(amb_path) as f:
            result = json.load(f)
        assert result["ambiguities"][0]["resolution"] == "planner-resolved"
        assert result["ambiguities"][0]["resolved_by"] == "planner"


# ─── build_digest_prompt ─────────────────────────────────────────


class TestBuildDigestPrompt:
    def test_includes_spec_content(self, spec_dir):
        scan = scan_spec_directory(spec_dir)
        prompt = build_digest_prompt(spec_dir, scan)
        assert "=== FILE: README.md ===" in prompt
        assert "=== FILE: features.md ===" in prompt
        assert "Feature A" in prompt

    def test_master_file_first(self, spec_dir):
        scan = scan_spec_directory(spec_dir)
        prompt = build_digest_prompt(spec_dir, scan)
        readme_pos = prompt.find("=== FILE: README.md ===")
        features_pos = prompt.find("=== FILE: features.md ===")
        assert readme_pos < features_pos
