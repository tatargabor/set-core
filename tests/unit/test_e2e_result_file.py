"""E2E failure-ID extraction from the machine-readable result file (0b).

The gate used to derive its failure list by regexing Playwright's *list*
reporter. Reporter choice belongs to the project, and a measured consumer
forces `--reporter json`, so those lines never appear: the regex matched
nothing and the gate either cried "crash" or, on the baseline path, recorded
zero failures. These tests pin the result-file surface, its staleness guard,
and the refusal to compare IDs across surfaces.
"""

import json
import os
import sys
import time

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", "lib"))
sys.path.insert(
    0,
    os.path.join(os.path.dirname(__file__), "..", "..", "modules", "web"),
)

from set_project_web import gates  # noqa: E402


def _write_result(root, payload, mtime=None):
    path = os.path.join(root, ".e2e", "last-run.json")
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w") as fh:
        json.dump(payload, fh)
    if mtime is not None:
        os.utime(path, (mtime, mtime))
    return path


FAILING_PAYLOAD = {
    "ok": False,
    "total": 12,
    "passed": 10,
    "failed": 2,
    "flaky": 0,
    "skipped": 0,
    "failures": [
        {"file": "tests/e2e/checkout.spec.ts", "title": "rejects an empty cart",
         "message": "expected 1 got 0"},
        {"file": "tests/e2e/auth.spec.ts", "title": "logs in", "message": "timeout"},
    ],
}

# Playwright list-reporter output for the same two failures.
LIST_OUTPUT = """
Running 12 tests using 4 workers

  1) [chromium] › tests/e2e/checkout.spec.ts:14:3 › rejects an empty cart
     Error: expected 1 got 0

  2) [chromium] › tests/e2e/auth.spec.ts:9:3 › logs in
     Error: timeout
"""


class TestResultFileReading:
    def test_failures_keyed_on_file_and_title(self, tmp_path):
        root = str(tmp_path)
        _write_result(root, FAILING_PAYLOAD)

        ids = gates._extract_e2e_failure_ids("", root=root)

        assert ids == {
            "tests/e2e/checkout.spec.ts::rejects an empty cart",
            "tests/e2e/auth.spec.ts::logs in",
        }

    def test_result_file_wins_over_console_output(self, tmp_path):
        """The file is authoritative — output may be any reporter's format."""
        root = str(tmp_path)
        _write_result(
            root,
            {"ok": False, "failures": [
                {"file": "tests/e2e/only.spec.ts", "title": "the real one"}]},
        )

        ids = gates._extract_e2e_failure_ids(LIST_OUTPUT, root=root)

        assert ids == {"tests/e2e/only.spec.ts::the real one"}

    def test_json_reporter_output_yields_nothing_without_the_file(self, tmp_path):
        """The bug being fixed: JSON reporter output has no list-format lines."""
        json_reporter_output = json.dumps(
            {"suites": [{"title": "checkout", "specs": [{"ok": False}]}]}
        )

        assert gates._extract_e2e_failure_ids(json_reporter_output) == set()
        assert gates._extract_e2e_failure_ids(
            json_reporter_output, root=str(tmp_path)
        ) == set()

    def test_ids_are_line_free(self, tmp_path):
        """A line insertion above a failing test must not create a 'new' failure."""
        root = str(tmp_path)
        _write_result(root, FAILING_PAYLOAD)

        ids = gates._extract_e2e_failure_ids("", root=root)

        assert not any(":14:" in i or ":9:" in i for i in ids)

    def test_empty_failures_with_ok_true(self, tmp_path):
        root = str(tmp_path)
        _write_result(root, {"ok": True, "total": 5, "passed": 5, "failures": []})

        parsed = gates._read_e2e_result_file(root)

        assert parsed is not None
        assert parsed["ok"] is True
        assert parsed["failure_ids"] == set()

    def test_stats_are_carried(self, tmp_path):
        root = str(tmp_path)
        _write_result(root, FAILING_PAYLOAD)

        parsed = gates._read_e2e_result_file(root)

        assert parsed["stats"] == {
            "total": 12, "passed": 10, "failed": 2, "flaky": 0, "skipped": 0,
        }

    def test_entry_missing_title_still_counts(self, tmp_path):
        root = str(tmp_path)
        _write_result(
            root, {"ok": False, "failures": [{"file": "tests/e2e/a.spec.ts"}]}
        )

        assert gates._extract_e2e_failure_ids("", root=root) == {
            "tests/e2e/a.spec.ts::"
        }

    def test_entry_with_neither_file_nor_title_is_skipped(self, tmp_path):
        root = str(tmp_path)
        _write_result(
            root,
            {"ok": False, "failures": [{"message": "boom"},
                                       {"file": "tests/e2e/a.spec.ts", "title": "t"}]},
        )

        assert gates._extract_e2e_failure_ids("", root=root) == {
            "tests/e2e/a.spec.ts::t"
        }


class TestFallbackToTextParsing:
    def test_missing_file_falls_back(self, tmp_path):
        ids = gates._extract_e2e_failure_ids(LIST_OUTPUT, root=str(tmp_path))

        assert ids == {
            "tests/e2e/checkout.spec.ts:14",
            "tests/e2e/auth.spec.ts:9",
        }

    def test_malformed_json_falls_back(self, tmp_path):
        root = str(tmp_path)
        path = os.path.join(root, ".e2e", "last-run.json")
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, "w") as fh:
            fh.write("{not json")

        assert gates._extract_e2e_failure_ids(LIST_OUTPUT, root=root) == {
            "tests/e2e/checkout.spec.ts:14",
            "tests/e2e/auth.spec.ts:9",
        }

    def test_json_without_failures_list_falls_back(self, tmp_path):
        root = str(tmp_path)
        _write_result(root, {"ok": False, "total": 3})

        assert gates._extract_e2e_failure_ids(LIST_OUTPUT, root=root) == {
            "tests/e2e/checkout.spec.ts:14",
            "tests/e2e/auth.spec.ts:9",
        }

    def test_json_array_falls_back(self, tmp_path):
        root = str(tmp_path)
        path = os.path.join(root, ".e2e", "last-run.json")
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, "w") as fh:
            json.dump([1, 2, 3], fh)

        assert gates._read_e2e_result_file(root) is None

    def test_no_root_means_text_only(self, tmp_path):
        """Callers that pass no root keep the old behaviour exactly."""
        _write_result(str(tmp_path), FAILING_PAYLOAD)

        ids = gates._extract_e2e_failure_ids(LIST_OUTPUT)

        assert ids == {
            "tests/e2e/checkout.spec.ts:14",
            "tests/e2e/auth.spec.ts:9",
        }


class TestStaleness:
    """A run that dies before writing leaves the previous run's file behind."""

    def test_file_older_than_the_run_is_ignored(self, tmp_path):
        root = str(tmp_path)
        # Previous run's file: green, and old.
        _write_result(root, {"ok": True, "failures": []},
                      mtime=time.time() - 3600)
        run_started = time.time()

        assert gates._read_e2e_result_file(root, min_mtime=run_started) is None

    def test_stale_green_file_does_not_mask_failures(self, tmp_path):
        """The false-green this guard exists to prevent."""
        root = str(tmp_path)
        _write_result(root, {"ok": True, "failures": []},
                      mtime=time.time() - 3600)
        run_started = time.time()

        ids = gates._extract_e2e_failure_ids(
            LIST_OUTPUT, root=root, min_mtime=run_started,
        )

        # Falls back to the console output, which does show failures.
        assert ids == {
            "tests/e2e/checkout.spec.ts:14",
            "tests/e2e/auth.spec.ts:9",
        }

    def test_file_written_during_the_run_is_used(self, tmp_path):
        root = str(tmp_path)
        run_started = time.time()
        _write_result(root, FAILING_PAYLOAD, mtime=run_started + 5)

        parsed = gates._read_e2e_result_file(root, min_mtime=run_started)

        assert parsed is not None
        assert len(parsed["failure_ids"]) == 2

    def test_grace_covers_coarse_timestamps(self, tmp_path):
        """Marginally-older mtime is accepted; filesystems round timestamps."""
        root = str(tmp_path)
        run_started = time.time()
        _write_result(root, FAILING_PAYLOAD, mtime=run_started - 1.0)

        assert gates._read_e2e_result_file(root, min_mtime=run_started) is not None


class TestConfigurablePath:
    def test_env_override(self, tmp_path, monkeypatch):
        root = str(tmp_path)
        custom = os.path.join(root, "reports", "e2e.json")
        os.makedirs(os.path.dirname(custom), exist_ok=True)
        with open(custom, "w") as fh:
            json.dump(FAILING_PAYLOAD, fh)
        monkeypatch.setenv("SET_E2E_RESULT_FILE", "reports/e2e.json")

        assert len(gates._extract_e2e_failure_ids("", root=root)) == 2

    def test_profile_hook(self, tmp_path):
        root = str(tmp_path)
        custom = os.path.join(root, "out", "res.json")
        os.makedirs(os.path.dirname(custom), exist_ok=True)
        with open(custom, "w") as fh:
            json.dump(FAILING_PAYLOAD, fh)

        class P:
            def e2e_result_file(self):
                return "out/res.json"

        assert len(gates._extract_e2e_failure_ids("", root=root, profile=P())) == 2

    def test_env_beats_profile(self, tmp_path, monkeypatch):
        root = str(tmp_path)
        os.makedirs(os.path.join(root, "a"), exist_ok=True)
        with open(os.path.join(root, "a", "x.json"), "w") as fh:
            json.dump(FAILING_PAYLOAD, fh)
        monkeypatch.setenv("SET_E2E_RESULT_FILE", "a/x.json")

        class P:
            def e2e_result_file(self):
                return "never/used.json"

        assert len(gates._extract_e2e_failure_ids("", root=root, profile=P())) == 2

    def test_absolute_path_is_honoured(self, tmp_path, monkeypatch):
        target = tmp_path / "abs.json"
        with open(target, "w") as fh:
            json.dump(FAILING_PAYLOAD, fh)
        monkeypatch.setenv("SET_E2E_RESULT_FILE", str(target))

        assert len(gates._extract_e2e_failure_ids("", root="/nonexistent")) == 2

    def test_profile_hook_raising_falls_back_to_default(self, tmp_path):
        root = str(tmp_path)
        _write_result(root, FAILING_PAYLOAD)

        class P:
            def e2e_result_file(self):
                raise RuntimeError("boom")

        assert len(gates._extract_e2e_failure_ids("", root=root, profile=P())) == 2

    def test_default_when_profile_lacks_hook(self, tmp_path):
        root = str(tmp_path)
        _write_result(root, FAILING_PAYLOAD)

        class P:
            pass

        assert len(gates._extract_e2e_failure_ids("", root=root, profile=P())) == 2


class TestFailureSource:
    """The baseline comparison must not mix key shapes."""

    def test_reports_result_file(self, tmp_path):
        root = str(tmp_path)
        _write_result(root, FAILING_PAYLOAD)

        assert gates._e2e_failure_source(root=root) == "result-file"

    def test_reports_text_without_a_file(self, tmp_path):
        assert gates._e2e_failure_source(root=str(tmp_path)) == "text"

    def test_reports_text_when_file_is_stale(self, tmp_path):
        root = str(tmp_path)
        _write_result(root, FAILING_PAYLOAD, mtime=time.time() - 3600)

        assert gates._e2e_failure_source(
            root=root, min_mtime=time.time()
        ) == "text"

    def test_id_shapes_differ_between_surfaces(self, tmp_path):
        """Why mixing them is unsafe: no key from one matches the other."""
        root = str(tmp_path)
        _write_result(root, FAILING_PAYLOAD)

        from_file = gates._extract_e2e_failure_ids("", root=root)
        from_text = gates._extract_e2e_failure_ids(LIST_OUTPUT)

        assert from_file.isdisjoint(from_text)


class TestUnattributedFailure:
    """`ok: false` with an empty failure list is a failure, not a pass."""

    def test_parsed_shape(self, tmp_path):
        root = str(tmp_path)
        _write_result(root, {"ok": False, "total": 0, "failures": []})

        parsed = gates._read_e2e_result_file(root)

        assert parsed["ok"] is False
        assert parsed["failure_ids"] == set()

    def test_extraction_returns_empty_so_gate_takes_the_fail_branch(self, tmp_path):
        root = str(tmp_path)
        _write_result(root, {"ok": False, "failures": []})

        # Empty set → the gate's `if not wt_failures:` unparseable/fail path.
        # It must NOT reach the baseline branch, which could pass the run.
        assert gates._extract_e2e_failure_ids("", root=root) == set()

    def test_ok_missing_is_recorded_as_unknown(self, tmp_path):
        root = str(tmp_path)
        _write_result(root, {"failures": []})

        assert gates._read_e2e_result_file(root)["ok"] is None


class TestBaselineSchema:
    def test_constant_is_pinned(self):
        """Bumping the ID shape must bump the schema, or caches go stale wrong."""
        assert gates._E2E_BASELINE_SCHEMA == 2

    def test_default_path_constant(self):
        assert gates._E2E_RESULT_FILE_DEFAULT == ".e2e/last-run.json"
