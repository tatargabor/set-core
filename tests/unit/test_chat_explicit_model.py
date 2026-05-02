"""Tests for arch-cleanup-pre-model-config: chat.py always passes --model.

Verifies the contract: every claude invocation in `ChatSession._build_claude_cmd`
includes `--model <self.model>`, including on resumed sessions.
"""

import os
import sys
from pathlib import Path

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", "lib"))

# Avoid importing the whole module (FastAPI deps); construct ChatSession by
# stripping out unrelated init-time work via direct attribute set.
from set_orch.chat import ChatSession


def _make(model: str, session_id=None) -> ChatSession:
    s = ChatSession.__new__(ChatSession)
    s.project_name = "p"
    s.project_path = Path("/tmp")
    s.session_id = session_id
    s.model = model
    return s


def test_fresh_session_passes_model_and_permission_mode():
    s = _make("opus-4-6")
    cmd = s._build_claude_cmd("hello", context="")
    # --model is contiguous and present
    assert "--model" in cmd
    i = cmd.index("--model")
    assert cmd[i + 1] == "opus-4-6"
    # fresh session has --permission-mode auto, no --resume
    assert "--permission-mode" in cmd
    assert cmd[cmd.index("--permission-mode") + 1] == "auto"
    assert "--resume" not in cmd


def test_resumed_session_passes_model_no_permission_mode():
    s = _make("opus-4-6", session_id="abc-123")
    cmd = s._build_claude_cmd("hello", context="")
    # --model still present even on resume
    assert "--model" in cmd
    i = cmd.index("--model")
    assert cmd[i + 1] == "opus-4-6"
    # Resume present
    assert "--resume" in cmd
    assert cmd[cmd.index("--resume") + 1] == "abc-123"
    # No permission-mode (resume inherits from session creation)
    assert "--permission-mode" not in cmd


def test_model_change_between_resumes_is_honored():
    s = _make("sonnet", session_id="abc-123")
    cmd1 = s._build_claude_cmd("first", context="")
    assert cmd1[cmd1.index("--model") + 1] == "sonnet"
    s.model = "opus-4-6"
    cmd2 = s._build_claude_cmd("second", context="")
    assert cmd2[cmd2.index("--model") + 1] == "opus-4-6"
    assert "--resume" in cmd2  # still resumed


def test_model_appears_before_resume_in_argv():
    """The contract is `--model` BEFORE `--resume` so the current model
    wins over any session-side carry-over."""
    s = _make("opus-4-6", session_id="abc-123")
    cmd = s._build_claude_cmd("x", context="")
    assert cmd.index("--model") < cmd.index("--resume")


def test_context_inserted_when_present():
    s = _make("opus-4-6")
    cmd = s._build_claude_cmd("x", context="hello-context")
    assert "--append-system-prompt" in cmd
    i = cmd.index("--append-system-prompt")
    assert cmd[i + 1] == "hello-context"


def test_context_omitted_when_empty():
    s = _make("opus-4-6")
    cmd = s._build_claude_cmd("x", context="")
    assert "--append-system-prompt" not in cmd


def test_text_appears_after_double_dash():
    s = _make("opus-4-6")
    cmd = s._build_claude_cmd("user-text", context="")
    assert "--" in cmd
    assert cmd[cmd.index("--") + 1] == "user-text"
