"""The continuation carrier — `set_orch.fleet.continuation` (B-190).

Driven with the Stop payload measured on Claude Code 2.1.330 (`session_id`, `prompt_id`,
`stop_hook_active`, `last_assistant_message`, `transcript_path`), the wait detector's
verdict record written by the real `wait_detect` helpers, a fake outbound and suggester,
and an injected transcript standing in for the session moving on.
"""

from __future__ import annotations

import json
import subprocess
from datetime import datetime, timezone
from pathlib import Path

import pytest

from set_orch.fleet import continuation as ct
from set_orch.fleet import question_relay as qr
from set_orch.fleet import wait_detect as wd

SID = "90e7a586-661e-4baf"
MESSAGE = "Deployed the Multi-Output fix to staging; the smoke test passed."
ARMED = 1_000_000.0


def stop_input(prompt_id="8593cae2"):
    return {"session_id": SID, "prompt_id": prompt_id, "hook_event_name": "Stop", "cwd": "/x",
            "stop_hook_active": False, "last_assistant_message": MESSAGE, "transcript_path": "/t.jsonl"}


def config(**over):
    store = {qr.KEY_ENABLED: "true", qr.KEY_TARGET: "command", qr.KEY_COMMAND: "bridge be", qr.KEY_AUDIENCE: "DEV"}
    store.update(over)
    store = {k: v for k, v in store.items() if v is not None}
    return lambda key, project=None, default=None: store.get(key, default)


def verdict(base, word, turn="8593cae2"):
    qr._write_json(wd.verdict_path(SID, base), {"turn": turn, "verdict": word, "at": ARMED})


def iso(epoch):
    return datetime.fromtimestamp(epoch, tz=timezone.utc).isoformat().replace("+00:00", "Z")


class World:
    def __init__(self, base: Path, answer=None, answer_after=1, code=0, suggestion=("Staging is green.", ["Promote to the test system", "Write the release note"]),
                 events=None, by=None):
        self.base, self.answer, self.answer_after, self.code = base, answer, answer_after, code
        self.by = by
        self.suggestion = suggestion
        self.events = events or {}          # poll number -> callable(world)
        self.envelopes, self.t, self.polls, self.now = [], 0.0, 0, ARMED
        self.entries = [{"type": "assistant", "timestamp": iso(ARMED - 2), "message": {"content": []}}]
        self.suggested = []

    def run(self, cmd, payload):
        self.envelopes.append(json.loads(payload))
        return self.code

    def sleep(self, s):
        self.t += s
        self.now += s
        self.polls += 1
        if self.envelopes and self.answer is not None and self.polls == self.answer_after + self._posted_at:
            q = self.envelopes[-1]["questions"][0]
            body = {"valasz": self.answer, **({"by": self.by} if self.by else {})}
            (Path(q["valasz_tar"]) / f"{q['id']}__Q1.json").write_text(json.dumps(body))
        if self.polls in self.events:
            self.events[self.polls](self)

    @property
    def _posted_at(self):
        return getattr(self, "_p", 0)

    def suggester(self, message):
        self.suggested.append(message)
        self._p = self.polls
        return self.suggestion

    def decide(self, get=None, inp=None, env=None, on_timeout=None):
        return ct.continue_turn(inp or stop_input(), get=get or config(), run=self.run, on_timeout=on_timeout,
                                project_name=lambda c: "proj", suggester=self.suggester,
                                clock=lambda: self.t, wall=lambda: self.now, sleep=self.sleep,
                                read_entries=lambda p: list(self.entries), env=env or {}, base=self.base)


def test_continued_from_the_channel(tmp_path):
    """AC-7: DONE → posted with suggestions → a picked suggestion wakes the session with it."""
    verdict(tmp_path, "DONE")
    w = World(tmp_path, answer="→ Promote to the test system")
    text = w.decide()
    assert text and text.endswith("Continue with this instruction: Promote to the test system")
    q = w.envelopes[0]["questions"][0]
    assert q["optionsList"] == ["→ Promote to the test system", "→ Write the release note"]
    assert "Staging is green." in q["question"] and "proj" in q["question"]
    assert w.suggested == [MESSAGE]
    assert not qr.waiting_path(SID, tmp_path).exists()


def test_free_text_answer(tmp_path):
    verdict(tmp_path, "DONE")
    text = World(tmp_path, answer="run the e2e suite first").decide()
    assert text.endswith("run the e2e suite first")


@pytest.mark.parametrize("word", ["WAITING", "SELF", "SKIPPED", "UNKNOWN"])
def test_only_a_done_turn_is_posted(tmp_path, word):
    """AC-8: a WAITING turn belongs to the re-ask path; nothing else is posted either."""
    verdict(tmp_path, word)
    w = World(tmp_path, answer="x")
    assert w.decide() is None and w.envelopes == [] and w.suggested == []


def test_a_verdict_for_another_turn_is_not_this_one(tmp_path):
    verdict(tmp_path, "DONE", turn="older-turn")
    w = World(tmp_path, answer="x")
    assert w.decide() is None and w.envelopes == []
    assert w.t >= ct.VERDICT_WAIT_S


def test_verdict_arriving_while_waiting(tmp_path):
    """The detector runs beside this hook: its record may land a few seconds later."""
    w = World(tmp_path, answer="go", events={3: lambda w: verdict(tmp_path, "DONE")})
    assert w.decide().endswith("go")


def test_suggester_failure_still_posts_free_text_only(tmp_path):
    verdict(tmp_path, "DONE")
    w = World(tmp_path, answer="go on", suggestion=None)
    assert w.decide().endswith("go on")
    assert w.envelopes[0]["questions"][0]["optionsList"] == []


def test_the_owner_typed_first(tmp_path):
    """AC-10: the supersede hook removes the record at once; the carrier lets go, no wake."""
    verdict(tmp_path, "DONE")
    w = World(tmp_path, answer="go", answer_after=5,
              events={2: lambda w: ct.mark_superseded(SID, tmp_path, wall=lambda: w.now)})
    assert w.decide() is None
    assert not qr.waiting_path(SID, tmp_path).exists()


def test_a_late_answer_after_a_background_wake(tmp_path):
    """AC-11: the session produced a newer assistant turn; the arriving answer is dropped."""
    def woke(w):
        w.entries.append({"type": "assistant", "timestamp": iso(w.now), "message": {"content": []}})
    verdict(tmp_path, "DONE")
    w = World(tmp_path, answer="go", answer_after=3, events={3: woke})
    assert w.decide() is None


def test_a_newer_continuation_replaces_this_one(tmp_path):
    def rearm(w):
        rec = json.loads(qr.waiting_path(SID, tmp_path).read_text())
        qr._write_json(qr.waiting_path(SID, tmp_path), {**rec, "id": "relay-90e7a586-newer"})
    verdict(tmp_path, "DONE")
    w = World(tmp_path, answer="go", answer_after=4, events={2: rearm})
    assert w.decide() is None
    assert json.loads(qr.waiting_path(SID, tmp_path).read_text())["id"] == "relay-90e7a586-newer"


def test_a_supersede_before_this_hook_armed_is_not_a_supersede(tmp_path):
    """The wake's own UserPromptSubmit marker (measured) predates the next continuation."""
    ct.mark_superseded(SID, tmp_path, wall=lambda: ARMED - 5)
    verdict(tmp_path, "DONE")
    assert World(tmp_path, answer="go").decide().endswith("go")


def test_supersede_never_touches_a_permission_record(tmp_path):
    qr._write_json(qr.waiting_path(SID, tmp_path), {"id": "relay-x", "kind": "permission", "session_id": SID})
    ct.mark_superseded(SID, tmp_path)
    assert qr.waiting_path(SID, tmp_path).exists()


def test_switch_off_and_webhook_and_opt_out_do_nothing(tmp_path):
    verdict(tmp_path, "DONE")
    for get in (config(**{qr.KEY_ENABLED: None}),
                config(**{qr.KEY_TARGET: "webhook", qr.KEY_WEBHOOK: "https://h"}),
                config(**{ct.KEY_CONTINUE: "false"})):
        w = World(tmp_path, answer="go")
        assert w.decide(get=get) is None and w.envelopes == []


def test_record_and_logs_carry_no_text(tmp_path, caplog):
    caplog.set_level("DEBUG")
    seen = {}
    verdict(tmp_path, "DONE")
    w = World(tmp_path, answer="secret-answer", answer_after=2,
              events={1: lambda w: seen.update(json.loads(qr.waiting_path(SID, tmp_path).read_text()))})
    w.decide()
    assert seen["kind"] == "continuation" and seen["questions"] == 1
    blob = json.dumps(seen) + caplog.text + "".join(p.read_text() for p in tmp_path.rglob("*") if p.is_file())
    for text in ("Staging is green", "Promote", "secret-answer", "Multi-Output"):
        assert text not in blob


def test_parse_suggestions():
    assert ct.parse_suggestions("SUMMARY: done\nNEXT: a\nNEXT: b\nNEXT: c\nNEXT: d") == ("done", ["a", "b", "c"])
    assert ct.parse_suggestions("I think it is fine") is None
    assert ct.parse_suggestions("NEXT: only a step") == ("", ["only a step"])


def test_carrier_exit_code_contract(tmp_path):
    """0 with nothing when the relay is off; the supersede carrier never blocks a prompt."""
    root = Path(__file__).resolve().parents[2]
    env = {"PATH": "/usr/bin:/bin", "HOME": str(tmp_path), "SET_CONFIG_DIR": str(tmp_path / "cfg")}
    for name in ("set-hook-continue-relay", "set-hook-relay-supersede"):
        res = subprocess.run([str(root / "bin" / name)], input=json.dumps(stop_input()),
                             capture_output=True, text=True, env=env)
        assert res.returncode == 0 and res.stdout == "" and res.stderr == "", name


def test_typed_while_the_suggestions_were_made_is_never_posted(tmp_path):
    """The race the record removal cannot cover: the prompt lands before any record exists."""
    w = World(tmp_path, answer="go")
    orig = w.suggester

    def typed_meanwhile(message):
        ct.mark_superseded(SID, tmp_path, wall=lambda: w.now + 1)
        return orig(message)
    w.suggester = typed_meanwhile
    verdict(tmp_path, "DONE")
    assert w.decide() is None and w.envelopes == []


def test_a_headless_run_gets_no_continuation(tmp_path):
    """Measured 2026-11-24: 8 of 15 continuations that morning were timer-run `claude -p`
    checks — they exit at the turn's end, so "what next?" went to the channel for nobody.
    The runtime marks its children: CLAUDE_CODE_ENTRYPOINT=sdk-cli for -p, cli interactive."""
    verdict(tmp_path, "DONE")
    w = World(tmp_path, answer="→ Promote to the test system")
    assert w.decide(env={"CLAUDE_CODE_ENTRYPOINT": "sdk-cli"}) is None
    assert w.envelopes == [] and not qr.waiting_path(SID, tmp_path).exists()
    w2 = World(tmp_path, answer="→ Promote to the test system")
    assert w2.decide(env={"CLAUDE_CODE_ENTRYPOINT": "cli"}), "an interactive session is still continued"


def test_a_next_step_that_reaches_the_hooks_limit_is_handed_to_a_carrier(tmp_path):
    """B-250: measured 2026-11-26 21:54, a next step dropped off the board at 3300 s. On a
    timeout-only release the hook hands the job on, with what the carrier needs to post it
    again and to tell a superseded turn."""
    verdict(tmp_path, "DONE")
    jobs = []
    w = World(tmp_path, answer=None)
    assert w.decide(get=config(**{qr.KEY_TIMEOUT: "30"}), on_timeout=jobs.append) is None
    (job,) = jobs
    assert job["kind"] == qr.KIND_CONTINUATION and job["session_id"] == SID and job["armed"] == ARMED
    assert job["transcript"] == "/t.jsonl" and job["project"] == "proj" and job["prompt_id"] == "8593cae2"
    assert job["question"].startswith("✅ Finished") and job["options"] == [
        ct.NEXT_MARK + "Promote to the test system", ct.NEXT_MARK + "Write the release note"]
    assert not qr.waiting_path(SID, tmp_path).exists(), "the hook's own record is cleared; the carrier writes its own"


def test_only_a_timeout_hands_a_next_step_on(tmp_path):
    """Superseded, moved on, released from the fleet, switch off: the item no longer stands."""
    def woke(w):
        w.entries.append({"type": "assistant", "timestamp": iso(w.now), "message": {"content": []}})
    cases = [
        {2: lambda w: ct.mark_superseded(SID, tmp_path, wall=lambda: w.now)},
        {2: woke},
        {2: lambda w: qr.request_release(SID, tmp_path)},
    ]
    for events in cases:
        verdict(tmp_path, "DONE")
        jobs = []
        w = World(tmp_path, answer=None, events=events)
        assert w.decide(get=config(**{qr.KEY_TIMEOUT: "30"}), on_timeout=jobs.append) is None
        assert jobs == [], events
        qr.release_path(SID, tmp_path).unlink(missing_ok=True)
        ct.supersede_path(SID, tmp_path).unlink(missing_ok=True)


def test_a_failing_hand_on_leaves_the_session_as_before(tmp_path):
    verdict(tmp_path, "DONE")
    w = World(tmp_path, answer=None)
    assert w.decide(get=config(**{qr.KEY_TIMEOUT: "30"}), on_timeout=lambda job: 1 / 0) is None


def test_an_auto_written_next_step_does_not_claim_the_owner_said_it(tmp_path):
    """B-246: measured 2026-11-26, an auto-written next step reached sessions as "The owner
    answered from the relay channel", and was built on as the owner's words."""
    verdict(tmp_path, "DONE")
    text = World(tmp_path, answer="→ Promote to the test system", by="auto-answer").decide()
    assert "The owner answered" not in text and "on the owner's behalf" in text and "did not type it" in text
    assert text.endswith("Promote to the test system")
    verdict(tmp_path, "DONE")
    own = World(tmp_path, answer="→ Promote to the test system").decide()
    assert own.startswith("The owner answered from the relay channel"), "the operator's own wording is unchanged"
