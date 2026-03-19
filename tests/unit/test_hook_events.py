"""Tests for set_hooks.events — routing, session start, user prompt, post tool, frustration."""

import json
import os
import sys
import tempfile
import shutil
from unittest.mock import patch, MagicMock

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", "lib"))

from set_hooks.events import (
    handle_event,
    handle_session_start,
    handle_user_prompt,
    handle_pre_tool,
    handle_post_tool,
    handle_post_tool_failure,
    handle_subagent_start,
    handle_subagent_stop,
    handle_stop,
    _extract_change_name,
    _commit_save,
    _extract_agent_summary,
)
from set_hooks.util import read_cache, write_cache


@pytest.fixture
def tmp_dir():
    d = tempfile.mkdtemp()
    yield d
    shutil.rmtree(d, ignore_errors=True)


@pytest.fixture
def cache_file(tmp_dir):
    return os.path.join(tmp_dir, "session-cache.json")


# ─── handle_event routing ────────────────────────────────────


class TestHandleEvent:
    def test_routes_to_session_start(self, cache_file):
        with patch("set_hooks.events.handle_session_start", return_value=None) as mock:
            handle_event("SessionStart", {"source": "startup"}, cache_file)
            mock.assert_called_once()

    def test_routes_to_user_prompt(self, cache_file):
        with patch("set_hooks.events.handle_user_prompt", return_value=None) as mock:
            handle_event("UserPromptSubmit", {"prompt": "test"}, cache_file)
            mock.assert_called_once()

    def test_routes_to_pre_tool(self, cache_file):
        result = handle_event("PreToolUse", {}, cache_file)
        assert result is None  # PreToolUse is disabled

    def test_routes_to_post_tool(self, cache_file):
        with patch("set_hooks.events.handle_post_tool", return_value=None) as mock:
            handle_event("PostToolUse", {"tool_name": "Read"}, cache_file)
            mock.assert_called_once()

    def test_routes_to_post_tool_failure(self, cache_file):
        with patch("set_hooks.events.handle_post_tool_failure", return_value=None) as mock:
            handle_event("PostToolUseFailure", {"error": "test"}, cache_file)
            mock.assert_called_once()

    def test_routes_to_stop(self, cache_file):
        with patch("set_hooks.events.handle_stop", return_value=None) as mock:
            handle_event("Stop", {}, cache_file)
            mock.assert_called_once()

    def test_unknown_event(self, cache_file):
        result = handle_event("UnknownEvent", {}, cache_file)
        assert result is None

    def test_passes_kwargs(self, cache_file):
        with patch("set_hooks.events.handle_stop", return_value=None) as mock:
            handle_event("Stop", {}, cache_file, set_tools_root="/foo")
            _, kwargs = mock.call_args
            assert kwargs.get("set_tools_root") == "/foo"


# ─── handle_pre_tool ──────────────────────────────────────────


class TestHandlePreTool:
    def test_always_returns_none(self, cache_file):
        result = handle_pre_tool({"tool_name": "Read"}, cache_file)
        assert result is None


# ─── handle_post_tool ─────────────────────────────────────────


class TestHandlePostTool:
    def test_skips_non_read_bash(self, cache_file):
        result = handle_post_tool(
            {"tool_name": "Write", "tool_input": {"file_path": "/foo"}},
            cache_file,
        )
        assert result is None

    @patch("set_hooks.events.recall_memories", return_value=None)
    def test_read_no_memories(self, mock_recall, cache_file):
        result = handle_post_tool(
            {"tool_name": "Read", "tool_input": {"file_path": "/a/b/c.py"}},
            cache_file,
        )
        assert result is None

    @patch("set_hooks.events.recall_memories", return_value="  - [MEM#1234] something")
    def test_read_with_memories(self, mock_recall, cache_file):
        result = handle_post_tool(
            {"tool_name": "Read", "tool_input": {"file_path": "/a/b/c.py"}},
            cache_file,
        )
        assert result is not None
        parsed = json.loads(result)
        assert "MEMORY" in parsed["hookSpecificOutput"]["additionalContext"]

    @patch("set_hooks.events.recall_memories", return_value="  - [MEM#1234] something")
    def test_dedup_second_call(self, mock_recall, cache_file):
        input_data = {"tool_name": "Read", "tool_input": {"file_path": "/a/b/c.py"}}
        # First call should return memories
        result1 = handle_post_tool(input_data, cache_file)
        assert result1 is not None
        # Second call with same file should be deduped
        result2 = handle_post_tool(input_data, cache_file)
        assert result2 is None


# ─── handle_post_tool_failure ─────────────────────────────────


class TestHandlePostToolFailure:
    def test_skips_interrupt(self, cache_file):
        result = handle_post_tool_failure(
            {"is_interrupt": True, "error": "something went wrong"},
            cache_file,
        )
        assert result is None

    def test_skips_short_error(self, cache_file):
        result = handle_post_tool_failure(
            {"error": "err"},
            cache_file,
        )
        assert result is None

    @patch("set_hooks.events.recall_memories", return_value="  - [MEM#abcd] past fix")
    def test_returns_past_fix(self, mock_recall, cache_file):
        result = handle_post_tool_failure(
            {"error": "Error: module not found, traceback follows" + "x" * 50},
            cache_file,
        )
        assert result is not None
        parsed = json.loads(result)
        assert "Past fix" in parsed["hookSpecificOutput"]["additionalContext"]


# ─── _extract_change_name ─────────────────────────────────────


class TestExtractChangeName:
    def test_opsx_apply(self):
        assert _extract_change_name("/opsx:apply my-change") == "my-change"

    def test_opsx_verify(self):
        assert _extract_change_name("/opsx:verify some-fix") == "some-fix"

    def test_opsx_ff(self):
        assert _extract_change_name("/opsx:ff new-feature") == "new-feature"

    def test_no_match(self):
        assert _extract_change_name("just a regular prompt") == ""

    def test_openspec_apply(self):
        assert _extract_change_name("/openspec-apply my-change") == "my-change"


# ─── _commit_save ─────────────────────────────────────────────


class TestCommitSave:
    @patch("set_hooks.events.subprocess.run")
    def test_heredoc_pattern(self, mock_run, cache_file):
        mock_run.return_value = MagicMock(returncode=0)
        input_data = {
            "tool_input": {
                "command": (
                    'git commit -m "$(cat <<\'EOF\'\n'
                    "feat: add new feature\n"
                    "\n"
                    "Co-Authored-By: Claude <noreply@anthropic.com>\n"
                    "EOF\n"
                    ')"'
                )
            }
        }
        _commit_save(input_data, cache_file)
        mock_run.assert_called_once()
        call_kwargs = mock_run.call_args
        assert "Committed: feat: add new feature" in call_kwargs.kwargs.get("input", "")

    @patch("set_hooks.events.subprocess.run")
    def test_simple_m_flag(self, mock_run, cache_file):
        mock_run.return_value = MagicMock(returncode=0)
        input_data = {
            "tool_input": {"command": 'git commit -m "fix: bug"'}
        }
        _commit_save(input_data, cache_file)
        mock_run.assert_called_once()

    @patch("set_hooks.events.subprocess.run")
    def test_dedup(self, mock_run, cache_file):
        mock_run.return_value = MagicMock(returncode=0)
        input_data = {
            "tool_input": {"command": 'git commit -m "fix: same commit"'}
        }
        _commit_save(input_data, cache_file)
        _commit_save(input_data, cache_file)
        # Should only call once due to dedup
        assert mock_run.call_count == 1

    def test_no_commit_message(self, cache_file):
        input_data = {"tool_input": {"command": "git status"}}
        # Should not crash
        _commit_save(input_data, cache_file)


# ─── _extract_agent_summary ──────────────────────────────────


class TestExtractAgentSummary:
    def test_extracts_last_entries(self, tmp_dir):
        path = os.path.join(tmp_dir, "agent.jsonl")
        entries = [
            {"type": "assistant", "message": {"content": [{"type": "text", "text": f"Entry {i}"}]}}
            for i in range(5)
        ]
        with open(path, "w") as f:
            for e in entries:
                f.write(json.dumps(e) + "\n")
        result = _extract_agent_summary(path)
        assert "Entry 2" in result
        assert "Entry 3" in result
        assert "Entry 4" in result

    def test_nonexistent_file(self):
        result = _extract_agent_summary("/tmp/nonexistent-agent.jsonl")
        assert result == ""

    def test_empty_file(self, tmp_dir):
        path = os.path.join(tmp_dir, "empty.jsonl")
        with open(path, "w") as f:
            pass
        result = _extract_agent_summary(path)
        assert result == ""


# ─── handle_subagent_start ────────────────────────────────────


class TestHandleSubagentStart:
    def test_empty_prompt(self, cache_file):
        result = handle_subagent_start({"tool_input": {}}, cache_file)
        assert result is None

    @patch("set_hooks.events.proactive_context", return_value="  - [MEM#5678] context")
    def test_with_prompt(self, mock_proactive, cache_file):
        result = handle_subagent_start(
            {"tool_input": {"prompt": "do something useful"}},
            cache_file,
        )
        assert result is not None
        parsed = json.loads(result)
        assert "subagent" in parsed["hookSpecificOutput"]["additionalContext"].lower()


# ─── handle_session_start ─────────────────────────────────────


class TestHandleSessionStart:
    @patch("set_hooks.events.proactive_context", return_value=None)
    @patch("set_hooks.events._recall_cheat_sheet", return_value="")
    def test_no_context_returns_none(self, mock_cheat, mock_proactive, cache_file):
        result = handle_session_start({"source": "startup"}, cache_file)
        assert result is None

    @patch("set_hooks.events.proactive_context", return_value="  - [MEM#abcd] project ctx")
    @patch("set_hooks.events._recall_cheat_sheet", return_value="  - cheat entry")
    def test_with_context(self, mock_cheat, mock_proactive, cache_file):
        result = handle_session_start({"source": "startup"}, cache_file)
        assert result is not None
        parsed = json.loads(result)
        ctx = parsed["hookSpecificOutput"]["additionalContext"]
        assert "CHEAT SHEET" in ctx
        assert "PROJECT CONTEXT" in ctx

    @patch("set_hooks.events.proactive_context", return_value=None)
    @patch("set_hooks.events._recall_cheat_sheet", return_value="")
    def test_clears_dedup_on_startup(self, mock_cheat, mock_proactive, cache_file):
        write_cache(cache_file, {"some_key": 1, "turn_count": 3})
        handle_session_start({"source": "startup"}, cache_file)
        cache = read_cache(cache_file)
        assert "some_key" not in cache
        assert cache.get("turn_count") == 3  # Preserved


# ─── handle_user_prompt ───────────────────────────────────────


class TestHandleUserPrompt:
    def test_empty_prompt_returns_none(self, cache_file):
        result = handle_user_prompt({"prompt": ""}, cache_file)
        assert result is None

    @patch("set_hooks.events.proactive_context", return_value="  - [MEM#1111] relevant")
    @patch("set_hooks.events.load_matching_rules", return_value="")
    def test_increments_turn_count(self, mock_rules, mock_proactive, cache_file):
        handle_user_prompt({"prompt": "test prompt"}, cache_file)
        cache = read_cache(cache_file)
        assert cache.get("turn_count") == 1

    @patch("set_hooks.events.proactive_context", return_value="  - [MEM#2222] relevant")
    @patch("set_hooks.events.load_matching_rules", return_value="")
    def test_returns_memory_context(self, mock_rules, mock_proactive, cache_file):
        result = handle_user_prompt({"prompt": "test prompt"}, cache_file)
        assert result is not None
        parsed = json.loads(result)
        assert "PROJECT MEMORY" in parsed["hookSpecificOutput"]["additionalContext"]
