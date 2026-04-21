from __future__ import annotations

from pathlib import Path

from set_orch.forensics.jsonl_reader import (
    CLEAN_STOP_REASONS,
    extract_bash_exit_code,
    extract_stop_reason,
    extract_text_content,
    is_error_result,
    is_permission_denial,
    is_user_interrupt,
    iter_records,
)


def test_iter_records_skips_malformed(tmp_path, caplog):
    path = tmp_path / "session.jsonl"
    path.write_text(
        '{"type":"user","message":{"role":"user","content":"hi"}}\n'
        "this is not json\n"
        '{"type":"assistant","message":{"role":"assistant","stop_reason":"end_turn"}}\n'
    )
    records = list(iter_records(path))
    assert len(records) == 2
    assert records[0]["type"] == "user"
    assert records[1]["type"] == "assistant"
    assert any("malformed" in r.message for r in caplog.records)


def test_is_error_result_detects_is_error_flag():
    block = {"type": "tool_result", "is_error": True, "content": "boom"}
    assert is_error_result(block) is True
    block2 = {"type": "tool_result", "is_error": False, "content": "ok"}
    assert is_error_result(block2) is False
    block3 = {"type": "tool_use", "name": "Bash"}
    assert is_error_result(block3) is False


def test_extract_bash_exit_code_from_text_content():
    block = {
        "type": "tool_result",
        "content": "npm ERR!\nexit code: 1",
    }
    assert extract_bash_exit_code(block) == 1

    block2 = {
        "type": "tool_result",
        "content": [{"type": "text", "text": "Done\nexit code: 0"}],
    }
    assert extract_bash_exit_code(block2) == 0

    block3 = {
        "type": "tool_result",
        "content": [{"type": "text", "text": '{"exitCode": 127, "stdout": "..."}'}],
    }
    assert extract_bash_exit_code(block3) == 127

    block4 = {"type": "tool_result", "content": "no exit code here"}
    assert extract_bash_exit_code(block4) is None


def test_extract_stop_reason_and_clean_set():
    record = {"type": "assistant", "message": {"stop_reason": "end_turn"}}
    assert extract_stop_reason(record) == "end_turn"
    assert "end_turn" in CLEAN_STOP_REASONS
    assert "max_tokens" not in CLEAN_STOP_REASONS
    record2 = {"type": "user"}
    assert extract_stop_reason(record2) is None


def test_is_user_interrupt_marker_and_flag():
    record_flag = {"type": "user", "isInterrupt": True, "message": {"content": "noop"}}
    assert is_user_interrupt(record_flag) is True

    record_text = {
        "type": "user",
        "message": {
            "role": "user",
            "content": "[Request interrupted by user] Stopping here.",
        },
    }
    assert is_user_interrupt(record_text) is True

    record_clean = {"type": "user", "message": {"content": "hello"}}
    assert is_user_interrupt(record_clean) is False


def test_permission_denial_in_tool_result():
    record = {
        "type": "user",
        "message": {
            "role": "user",
            "content": [
                {
                    "type": "tool_result",
                    "content": "Claude requested permissions to edit /x which is a sensitive file.",
                    "is_error": True,
                    "tool_use_id": "toolu_1",
                }
            ],
        },
    }
    assert is_permission_denial(record) is True


def test_extract_text_content_handles_list_and_str():
    # String content.
    block = {"type": "tool_result", "content": "hello"}
    assert extract_text_content(block) == "hello"

    # List content with text sub-blocks.
    block2 = {
        "type": "tool_result",
        "content": [{"type": "text", "text": "line 1"}, {"type": "text", "text": "line 2"}],
    }
    assert extract_text_content(block2) == "line 1\nline 2"

    # Whole record.
    record = {
        "type": "assistant",
        "message": {
            "role": "assistant",
            "content": [
                {"type": "thinking", "thinking": "think hard"},
                {"type": "text", "text": "visible"},
            ],
        },
    }
    text = extract_text_content(record)
    assert "think hard" in text
    assert "visible" in text
