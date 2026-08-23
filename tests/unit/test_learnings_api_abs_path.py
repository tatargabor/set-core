"""The API is where a stored relative finding path becomes an openable one.

It is the right place because the server knows the project root and its response is never
committed — so resolving here adds no absolute path to any artifact. What it must NOT do is
overwrite `file`: that value is what fingerprints and committed artifacts carry.
"""

import json
from pathlib import Path

import pytest

from set_orch.api.learnings import _annotate_absolute_paths, _read_review_findings
from set_orch.finding_paths import BASE_FIELD


ROOT = Path("/home/u/p")


class TestAnnotateAbsolutePaths:
    def test_relative_file_gains_an_absolute_sibling(self):
        entries = [{"change": "c", "issues": [{"file": "src/a.ts"}]}]
        _annotate_absolute_paths(entries, ROOT)
        issue = entries[0]["issues"][0]
        assert issue["file_abs"] == "/home/u/p/src/a.ts"

    def test_stored_file_is_left_untouched(self):
        entries = [{"change": "c", "issues": [{"file": "src/a.ts"}]}]
        _annotate_absolute_paths(entries, ROOT)
        assert entries[0]["issues"][0]["file"] == "src/a.ts"

    def test_issue_with_no_file_gets_empty_not_the_bare_root(self):
        # Returning the project root would render as a path pointing at a directory the
        # finding is not about — openable, and wrong.
        entries = [{"change": "c", "issues": [{"file": ""}, {"summary": "no file key"}]}]
        _annotate_absolute_paths(entries, ROOT)
        assert entries[0]["issues"][0]["file_abs"] == ""
        assert entries[0]["issues"][1]["file_abs"] == ""

    def test_entry_without_a_base_resolves_as_repo_root(self):
        # Everything written before this change looks like this. Failing here would drop
        # the path from every historical finding.
        entries = [{"change": "c", "issues": [{"file": "src/a.ts"}]}]
        assert BASE_FIELD not in entries[0]
        _annotate_absolute_paths(entries, ROOT)
        assert entries[0]["issues"][0]["file_abs"] == "/home/u/p/src/a.ts"

    def test_unknown_base_yields_empty_rather_than_a_wrong_join(self):
        entries = [{"change": "c", BASE_FIELD: "something-else",
                    "issues": [{"file": "src/a.ts"}]}]
        _annotate_absolute_paths(entries, ROOT)
        assert entries[0]["issues"][0]["file_abs"] == ""

    def test_malformed_entries_do_not_raise(self):
        entries = ["not a dict", {"change": "c"}, {"change": "d", "issues": None},
                   {"change": "e", "issues": ["not a dict"]}]
        _annotate_absolute_paths(entries, ROOT)  # must not raise


class TestReadReviewFindingsResponse:
    def _project(self, tmp_path, entry):
        d = tmp_path / "set" / "orchestration"
        d.mkdir(parents=True)
        (d / "review-findings.jsonl").write_text(json.dumps(entry) + "\n")
        return tmp_path

    def test_endpoint_payload_carries_the_resolved_path(self, tmp_path):
        project = self._project(tmp_path, {
            "change": "add-orders", "timestamp": "t", "attempt": 1,
            BASE_FIELD: "repo-root",
            "issue_count": 1, "critical_count": 1, "high_count": 0,
            "issues": [{"severity": "CRITICAL", "summary": "IDOR", "file": "src/a.ts",
                        "line": "12", "fix": "guard it"}],
        })
        data = _read_review_findings(project)
        issue = data["entries"][0]["issues"][0]
        assert issue["file_abs"] == str(project / "src/a.ts")
        assert issue["file"] == "src/a.ts"

    def test_no_findings_file_returns_empty_without_raising(self, tmp_path):
        data = _read_review_findings(tmp_path)
        assert data["entries"] == []
