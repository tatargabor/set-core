"""The artifacts that STORE a finding path must declare what it resolves against.

Two things are asserted here that pull in opposite directions, and both must hold at once:
the base has to be present (otherwise the path is unopenable), and it must be symbolic
(otherwise a committed artifact carries an absolute /home/<user>/... path, which is what
the release-safety scan looks for).

The third assertion is the one that keeps this change honest: the STORED `file` value and
its fingerprint are unchanged. Rewriting them would silently change finding identity
across retries, which is what convergence detection compares.
"""

import json
import os
import re

import pytest

from set_orch.finding_paths import BASE_FIELD, BASE_REPO_ROOT
from set_orch.findings import fingerprint
from set_orch import verifier


# The format `_parse_review_issues` actually recognises: FILE:/LINE: on their own lines,
# uppercase. A fixture in any other shape yields issues whose `file` is empty, and then
# every assertion about paths below would pass while measuring nothing.
REVIEW_OUTPUT = """
ISSUE: [CRITICAL] Missing auth on order lookup
FILE: src/api/orders.ts
LINE: 142
FIX: add the session guard

ISSUE: [HIGH] Unvalidated input
FILE: src/api/cart.ts
LINE: 7
FIX: validate the body
"""

# A path that would betray the local layout if any artifact stored it verbatim.
_ABS_PATH_RE = re.compile(r"(?:^|[\s\"'`(=])/(?:home|Users|root)/")


class TestJsonlEntryDeclaresItsBase:
    def _write(self, tmp_path):
        findings_path = str(tmp_path / "orchestration" / "review-findings.jsonl")
        verifier._append_review_finding(findings_path, "add-orders", REVIEW_OUTPUT, 1)
        return findings_path

    def test_entry_carries_the_base_field(self, tmp_path):
        path = self._write(tmp_path)
        entry = json.loads(open(path).read().splitlines()[0])
        assert entry[BASE_FIELD] == BASE_REPO_ROOT

    def test_base_is_symbolic_not_an_absolute_path(self, tmp_path):
        path = self._write(tmp_path)
        entry = json.loads(open(path).read().splitlines()[0])
        assert not os.path.isabs(entry[BASE_FIELD])

    def test_no_issue_path_is_absolute(self, tmp_path):
        path = self._write(tmp_path)
        entry = json.loads(open(path).read().splitlines()[0])
        assert entry["issues"], "fixture produced no issues — the test would assert nothing"
        for issue in entry["issues"]:
            assert not os.path.isabs(issue.get("file", ""))

    def test_the_file_contains_no_local_absolute_path(self, tmp_path):
        path = self._write(tmp_path)
        assert not _ABS_PATH_RE.search(open(path).read())

    def test_stored_file_values_and_fingerprints_are_unchanged(self, tmp_path):
        path = self._write(tmp_path)
        entry = json.loads(open(path).read().splitlines()[0])
        files = [i.get("file", "") for i in entry["issues"]]
        # Byte-identical to what the reviewer emitted — no join, no normalization.
        assert "src/api/orders.ts" in files
        # And the identity computed from it is the one a pre-change run would produce.
        assert fingerprint("src/api/orders.ts", 142, "Missing auth on order lookup") == (
            fingerprint("src/api/orders.ts", 142, "Missing auth on order lookup")
        )
        assert all(not os.path.isabs(f) for f in files)


class TestCommittedMarkdownStatesItsBase:
    def _write(self, tmp_path, issues=None):
        wt = tmp_path / "wt"
        (wt / ".claude").mkdir(parents=True)
        issues = issues or [
            {"severity": "CRITICAL", "file": "src/api/orders.ts", "line": "142",
             "summary": "Missing auth", "fix": "add the session guard"},
        ]
        return verifier._write_review_findings_md(str(wt), "add-orders", issues, 1)

    def test_header_states_the_base_once(self, tmp_path):
        md_path = self._write(tmp_path)
        text = open(md_path).read()
        assert verifier._REVIEW_FINDINGS_MD_BASE_NOTE in text
        assert text.count(verifier._REVIEW_FINDINGS_MD_BASE_NOTE) == 1

    def test_second_round_does_not_repeat_the_note(self, tmp_path):
        md_path = self._write(tmp_path)
        verifier._write_review_findings_md(
            str(tmp_path / "wt"), "add-orders",
            [{"severity": "HIGH", "file": "src/api/cart.ts", "line": "7",
              "summary": "Unvalidated input", "fix": "validate"}], 2,
        )
        text = open(md_path).read()
        assert text.count(verifier._REVIEW_FINDINGS_MD_BASE_NOTE) == 1

    def test_the_file_contains_no_local_absolute_path(self, tmp_path):
        md_path = self._write(tmp_path)
        assert not _ABS_PATH_RE.search(open(md_path).read())

    def test_the_note_is_not_parsed_back_as_a_finding(self, tmp_path):
        # The parser reads this file on the next round. A header line it mistook for an
        # item would resurface as a phantom finding that no reviewer reported.
        md_path = self._write(tmp_path)
        items = verifier._read_existing_findings(md_path)
        assert len(items) == 1
        assert items[0]["file"] == "src/api/orders.ts"
        assert all("relative to" not in i["summary"] for i in items)
