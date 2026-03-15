"""Tests for wt_hooks.stop — metrics flush, transcript extraction, commit save, checkpoint."""

import json
import os
import sys
import tempfile
import shutil

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", "lib"))

from wt_hooks.stop import (
    extract_insights,
    save_checkpoint,
    _filter_transcript,
    _save_design_choices,
)
from wt_hooks.util import read_cache, write_cache


@pytest.fixture
def tmp_dir():
    d = tempfile.mkdtemp()
    yield d
    shutil.rmtree(d, ignore_errors=True)


@pytest.fixture
def cache_file(tmp_dir):
    return os.path.join(tmp_dir, "session-cache.json")


@pytest.fixture
def transcript_file(tmp_dir):
    return os.path.join(tmp_dir, "transcript.jsonl")


# ─── _filter_transcript ──────────────────────────────────────


class TestFilterTranscript:
    def test_user_entries_skipped(self, transcript_file):
        """User messages are no longer extracted — they're ephemeral."""
        entries = [
            {"type": "user", "message": {"content": "This is a user prompt with enough characters"}},
        ]
        with open(transcript_file, "w") as f:
            for e in entries:
                f.write(json.dumps(e) + "\n")
        result = _filter_transcript(transcript_file)
        assert len(result) == 0

    def test_assistant_summary_extracted(self, transcript_file):
        """Long assistant text with insight keywords is extracted."""
        summary_text = "## Summary\n\n" + "Implementation complete. " * 20
        entries = [
            {
                "type": "assistant",
                "message": {
                    "content": [
                        {"type": "text", "text": summary_text},
                    ]
                },
            },
        ]
        with open(transcript_file, "w") as f:
            for e in entries:
                f.write(json.dumps(e) + "\n")
        result = _filter_transcript(transcript_file)
        assert len(result) == 1
        assert result[0]["role"] == "assistant"

    def test_short_assistant_filtered(self, transcript_file):
        """Short assistant text is filtered out."""
        entries = [
            {
                "type": "assistant",
                "message": {"content": [{"type": "text", "text": "short"}]},
            },
        ]
        with open(transcript_file, "w") as f:
            for e in entries:
                f.write(json.dumps(e) + "\n")
        result = _filter_transcript(transcript_file)
        assert len(result) == 0

    def test_routine_assistant_filtered(self, transcript_file):
        """Long assistant text WITHOUT insight keywords is filtered."""
        routine_text = "Let me read the file and check the contents. " * 10
        entries = [
            {
                "type": "assistant",
                "message": {
                    "content": [
                        {"type": "text", "text": routine_text},
                    ]
                },
            },
        ]
        with open(transcript_file, "w") as f:
            for e in entries:
                f.write(json.dumps(e) + "\n")
        result = _filter_transcript(transcript_file)
        assert len(result) == 0

    def test_tool_use_not_extracted(self, transcript_file):
        """Tool use entries (Bash, Read) are no longer extracted."""
        entries = [
            {
                "type": "assistant",
                "message": {
                    "content": [
                        {
                            "type": "tool_use",
                            "name": "Bash",
                            "input": {"command": "git status"},
                        },
                    ]
                },
            },
        ]
        with open(transcript_file, "w") as f:
            for e in entries:
                f.write(json.dumps(e) + "\n")
        result = _filter_transcript(transcript_file)
        assert len(result) == 0

    def test_error_in_tool_result(self, transcript_file):
        """Errors are still extracted (they're valuable)."""
        entries = [
            {
                "type": "tool_result",
                "content": "Error: file not found /missing.py — traceback follows with enough detail to be useful for debugging",
            },
        ]
        with open(transcript_file, "w") as f:
            for e in entries:
                f.write(json.dumps(e) + "\n")
        result = _filter_transcript(transcript_file)
        assert len(result) == 1
        assert "[Error]" in result[0]["content"]

    def test_nonexistent_file(self):
        result = _filter_transcript("/tmp/nonexistent-transcript.jsonl")
        assert result == []

    def test_max_entries_cap(self, transcript_file):
        """Hard cap at _MAX_EXTRACT_ENTRIES."""
        from wt_hooks.stop import _MAX_EXTRACT_ENTRIES
        entries = []
        for i in range(_MAX_EXTRACT_ENTRIES + 20):
            entries.append({
                "type": "tool_result",
                "content": f"Error #{i}: traceback some failure that should be captured in memory extraction",
            })
        with open(transcript_file, "w") as f:
            for e in entries:
                f.write(json.dumps(e) + "\n")
        result = _filter_transcript(transcript_file)
        assert len(result) == _MAX_EXTRACT_ENTRIES

    def test_content_truncation(self, transcript_file):
        """Long content is truncated to 1500 chars."""
        summary_text = "## Summary\n\n" + "X" * 3000
        entries = [
            {
                "type": "assistant",
                "message": {
                    "content": [
                        {"type": "text", "text": summary_text},
                    ]
                },
            },
        ]
        with open(transcript_file, "w") as f:
            for e in entries:
                f.write(json.dumps(e) + "\n")
        result = _filter_transcript(transcript_file)
        assert len(result) == 1
        assert len(result[0]["content"]) <= 1500


# ─── save_checkpoint ──────────────────────────────────────────


class TestSaveCheckpoint:
    def test_empty_metrics(self, cache_file):
        write_cache(cache_file, {"_metrics": []})
        # Returns False because no wt-memory command to run
        result = save_checkpoint(cache_file, 10, 0)
        # Can't test True without wt-memory available, but should not crash
        assert isinstance(result, bool)

    def test_with_metrics(self, cache_file):
        metrics = [
            {"event": "UserPromptSubmit", "query": "test query with enough length"},
            {"event": "PostToolUse", "query": "/foo/bar.py"},
            {"event": "PostToolUse", "query": "git status"},
        ]
        write_cache(cache_file, {"_metrics": metrics})
        result = save_checkpoint(cache_file, 5, 0)
        assert isinstance(result, bool)


# ─── _save_design_choices ─────────────────────────────────────


class TestSaveDesignChoices:
    def test_no_design_file(self, tmp_dir):
        marker = os.path.join(tmp_dir, "marker")
        # Should not crash
        _save_design_choices("nonexistent-change", marker)

    def test_already_saved(self, tmp_dir):
        marker = os.path.join(tmp_dir, "marker")
        design_dir = os.path.join(tmp_dir, "openspec", "changes", "test-change")
        os.makedirs(design_dir)
        with open(os.path.join(design_dir, "design.md"), "w") as f:
            f.write("**Choice**: Use Python\n")
        with open(marker, "w") as f:
            f.write("test-change\n")

        old_cwd = os.getcwd()
        try:
            os.chdir(tmp_dir)
            _save_design_choices("test-change", marker)
        finally:
            os.chdir(old_cwd)
        # Should be no-op since already in marker


# ─── heuristic regex ──────────────────────────────────────────


class TestHeuristicPatterns:
    def test_false_positive_not_extracted(self, transcript_file):
        """Short text without insight keywords is filtered out."""
        entries = [
            {
                "type": "assistant",
                "message": {
                    "content": [
                        {"type": "text", "text": "This was a false positive, the error is actually in another module and we should ignore it completely"},
                    ]
                },
            },
        ]
        with open(transcript_file, "w") as f:
            for e in entries:
                f.write(json.dumps(e) + "\n")
        result = _filter_transcript(transcript_file)
        # Too short (<200 chars) to be an insight, filtered out
        assert len(result) == 0
