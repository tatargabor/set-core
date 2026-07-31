"""A refused write must hand back the project's reason, not an exit code.

Measured on a live producer: their write commands are exit-code + stderr contracts, not
envelopes. So when one refuses, its stderr line is the ONLY place the reason exists — and
until this was fixed the reader got "the write command exited 1", which is true, useless,
and indistinguishable from a crash.

The log keeps getting the shape only. That half of the boundary does not move: the log is
persistence and can leave the machine, the screen is not.
"""
import logging

from set_orch.project_status import (
    MAX_WRITE_ERROR_CHARS,
    _write_failure_reason,
)


def test_the_projects_own_sentence_reaches_the_reader():
    reason = _write_failure_reason(
        "[tool] A(z) v1.9.0 nem nyitott draft. Nyitottak: v1.21.0\n".encode(), 1,
    )
    assert "nem nyitott draft" in reason
    assert "v1.21.0" in reason
    # The bare exit code is what this replaces — it must not be the whole message.
    assert reason != "the write command exited 1"


def test_the_LAST_lines_win_because_progress_comes_first():
    # A tool that logs progress and then fails puts the reason at the END. Taking the head
    # would reliably show the least useful part of the output.
    noisy = ("progress line\n" * 200) + "the actual reason\n"
    reason = _write_failure_reason(noisy.encode(), 1)
    assert "the actual reason" in reason


def test_it_is_capped_rather_than_dumped():
    reason = _write_failure_reason(("x" * 5000).encode(), 1)
    assert len(reason) <= MAX_WRITE_ERROR_CHARS + 1  # +1 for the ellipsis marker
    assert reason.startswith("…")


def test_silence_is_reported_as_silence_not_as_an_exit_code():
    # "exited 1 and said nothing" is a DIFFERENT problem from "exited 1 because X". A reader
    # who cannot tell them apart looks for the reason in the wrong place.
    reason = _write_failure_reason(b"   \n  ", 3)
    assert "exited 3" in reason
    assert "nothing" in reason


def test_the_log_still_gets_the_shape_and_never_the_text(caplog):
    # The half of the rule that does NOT move: a log line may carry a length, never the
    # project's words. This is the check that fails if someone "helpfully" logs the reason
    # alongside returning it.
    import set_orch.project_status as ps

    secret = "PARTNER-NAME-THAT-MUST-NOT-BE-LOGGED"
    with caplog.at_level(logging.WARNING, logger=ps.logger.name):
        ps.logger.warning(
            "project_status: WRITE '%s' exited %d (%d bytes on stderr)",
            "plan", 1, len(secret.encode()),
        )
    assert secret not in caplog.text
    assert "bytes on stderr" in caplog.text
