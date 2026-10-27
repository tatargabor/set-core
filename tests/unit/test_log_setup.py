"""B-162 — the long-running processes must not log DEBUG to stderr by default.

stderr is what systemd puts in the journal. The subprocess tests drive the real
CLI entry point, because the defect was in the wiring (`basicConfig(level=DEBUG)`
in `cli.main`), and a test of the helper alone would pass with the old wiring
still in place.
"""

import logging
import os
import subprocess
import sys
from pathlib import Path

from set_orch import log_setup

LIB = str(Path(__file__).resolve().parents[2] / "lib")

PROBE = f"""
import logging, sys
sys.path.insert(0, {LIB!r})
sys.argv = ['set-orch-core'] + sys.argv[1:] + ['--help']
from set_orch import cli
try:
    cli.main()
except SystemExit:
    pass
log = logging.getLogger('probe')
log.debug('PROBE-DEBUG')
log.info('PROBE-INFO')
"""


def _run(extra_args=(), env_level=None):
    env = {k: v for k, v in os.environ.items() if k != log_setup.ENV_VAR}
    if env_level is not None:
        env[log_setup.ENV_VAR] = env_level
    return subprocess.run(
        [sys.executable, "-c", PROBE, *extra_args],
        capture_output=True, text=True, env=env, timeout=120,
    )


def test_cli_stderr_drops_debug_by_default():
    result = _run()
    assert "PROBE-INFO" in result.stderr
    assert "PROBE-DEBUG" not in result.stderr


def test_cli_stderr_debug_when_asked():
    result = _run(env_level="debug")
    assert "PROBE-DEBUG" in result.stderr


def test_cli_run_log_file_keeps_debug(tmp_path):
    state = tmp_path / "state.json"
    result = _run(extra_args=("--state", str(state)))
    log_file = tmp_path / "set" / "orchestration" / "python.log"
    assert log_file.exists(), result.stderr
    assert "PROBE-DEBUG" in log_file.read_text()
    assert "PROBE-DEBUG" not in result.stderr


def test_invalid_level_falls_back_to_info_and_says_so():
    level, problem = log_setup.resolve_stream_level("loud")
    assert level == logging.INFO
    assert problem and "loud" in problem


def test_absent_or_blank_level_is_info_without_complaint():
    assert log_setup.resolve_stream_level(None) == (logging.INFO, None)
    assert log_setup.resolve_stream_level("  ") == (logging.INFO, None)


def test_root_level_is_the_lowest_handler_level(tmp_path):
    handlers, _ = log_setup.build_handlers(str(tmp_path / "x.log"), None)
    try:
        assert [h.level for h in handlers] == [logging.DEBUG, logging.INFO]
        assert log_setup.root_level(handlers) == logging.DEBUG
    finally:
        for h in handlers:
            h.close()
