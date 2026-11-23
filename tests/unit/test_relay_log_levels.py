"""service-log-hygiene (fleet-era-consolidation 5.2-5.3): a relay that times out is a normal
outcome — the question goes back to the terminal, exactly as on the three sibling release paths,
which log at INFO. Measured 2026-11-23: these two lines were the only WARNINGs in the relay log
over 24 hours (5 of 5)."""

from __future__ import annotations

import json
import logging

from set_orch.fleet import question_relay as qr

from test_question_relay import config, run_relay


def warnings(caplog):
    return [r for r in caplog.records if r.levelno >= logging.WARNING and r.name == qr.logger.name]


def test_a_question_timeout_is_info_not_warning(tmp_path, caplog):
    caplog.set_level(logging.DEBUG, logger=qr.logger.name)
    out, _, _ = run_relay(tmp_path, config(**{qr.KEY_TIMEOUT: "30"}))
    assert out is None
    assert any("no answer within" in r.getMessage() and r.levelno == logging.INFO for r in caplog.records)
    assert warnings(caplog) == []


def test_a_continuation_timeout_is_info_not_warning(tmp_path, caplog):
    caplog.set_level(logging.DEBUG, logger=qr.logger.name)
    record = {"session_id": "1bf7b969-5208", "kind": "continuation", "id": "relay-x"}
    path = qr.waiting_path(record["session_id"], tmp_path)
    path.parent.mkdir(parents=True)
    path.write_text(json.dumps(record))
    t = [0.0]
    out = qr.wait_one(record, get=config(**{qr.KEY_TIMEOUT: "5"}), clock=lambda: t[0],
                      sleep=lambda s: t.__setitem__(0, t[0] + s), base=tmp_path)
    assert out is None
    assert any("no answer within" in r.getMessage() and r.levelno == logging.INFO for r in caplog.records)
    assert warnings(caplog) == []
