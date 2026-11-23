"""The decider's core — `set_orch.fleet.auto_answer` (fleet-auto-answer, group 2).

The parser, the exclusions and the allow rule are pure and tested as tables, in both
directions. The fork and its bound are driven through a real fake `claude` script on PATH,
because what matters there — the argv, the process group, what is left alive — is a property
of real processes. The reference check reads a real transcript file in the runtime's shape.
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from types import SimpleNamespace

import pytest

from set_orch.fleet import auto_answer as aa

SID = "62a7c924-aa83-4969-9122-bbe6b2890df8"
ASKED = 2_000_000_000.0


def cfg(**over):
    store = {k: v for k, v in over.items() if v is not None}
    return lambda key, project=None, default=None: store.get(key, default)


def q(key="Q1", text="Which release colour?", options=("TEAL", "ORANGE"), multi=False):
    return aa.Question(key=key, text=text, options=list(options), multi=multi)


def env_of(*questions):
    return {"questions": [{"id": "relay-x", "key": x.key, "question": x.text, "optionsList": x.options,
                           "multi": x.multi, "audience": "DEV", "source": "p · s", "valasz_tar": "/a"}
                          for x in questions]}


# --------------------------------------------------------------------------- 2.1

def test_config_defaults():
    get = cfg()
    assert aa.enabled(get) is False and aa.forward_command(get) == ""
    assert aa.window_s(get) == 60.0 and aa.likely_min(get) == 0.8
    assert aa.fallback_model(get) == "sonnet" and aa.log_days(get) == 90
    assert aa.never_patterns(get) == [] and aa.extra_paths(get) == []


def test_config_values_and_bad_values():
    get = cfg(**{aa.KEY_ENABLED: "true", aa.KEY_WINDOW: "15", aa.KEY_LIKELY_MIN: "0.9",
                 aa.KEY_NEVER: '["szallitolevel", "invoice"]', aa.KEY_EXTRA: "docs/decisions.md\nnotes/"})
    assert aa.enabled(get) and aa.window_s(get) == 15.0 and aa.likely_min(get) == 0.9
    assert aa.never_patterns(get) == ["szallitolevel", "invoice"]
    assert aa.extra_paths(get) == ["docs/decisions.md", "notes/"]
    bad = cfg(**{aa.KEY_LIKELY_MIN: "1.5", aa.KEY_WINDOW: "soon"})
    assert aa.likely_min(bad) == 0.8 and aa.window_s(bad) == 60.0


# --------------------------------------------------------------------------- 2.2

def reply(**entry):
    base = {"key": "Q1", "choice": "TEAL", "tier": "decided", "confidence": 0.95, "outward": False,
            "references": [{"kind": "operator", "quote": "the release color is TEAL"}]}
    base.update(entry)
    return json.dumps({"answers": [base]})


def test_parser_accepts_a_sourced_decision():
    answers, refused = aa.parse_decision(reply(), [q()], aa.KIND_ASK)
    assert refused == {} and answers["Q1"].choice == "TEAL" and answers["Q1"].claimed_tier == "decided"
    assert answers["Q1"].references[0].kind == "operator"


def test_parser_reads_a_fenced_or_prose_wrapped_reply():
    wrapped = "Here it is:\n```json\n" + reply() + "\n```\nDone."
    assert "Q1" in aa.parse_decision(wrapped, [q()], aa.KIND_ASK)[0]


@pytest.mark.parametrize("raw,reason", [
    ("not json at all", "no JSON object in the reply"),
    (reply(tier=None), "missing or unknown tier"),
    (reply(tier="certain"), "missing or unknown tier"),
    (reply(references=[]), "tier decided without a reference"),
    (reply(tier="found", references=[{"kind": "file", "quote": "x" * 20}]), "tier found without a reference"),
    (reply(tier="likely", confidence=None, references=[]), "likely without a confidence in [0, 1]"),
    (reply(tier="likely", confidence=1.4, references=[]), "likely without a confidence in [0, 1]"),
    (reply(choice="PURPLE"), "choice outside the options"),
    (reply(choice=None), "abstained"),
    (json.dumps({"answers": [{"key": "Q2", "choice": "TEAL"}]}), "no entry for the question"),
])
def test_parser_refuses(raw, reason):
    answers, refused = aa.parse_decision(raw, [q()], aa.KIND_ASK)
    assert answers == {} and refused == {"Q1": reason}


def test_continuation_choice_may_be_free_text():
    c = q(text="What next?", options=["→ Promote", "→ Release note"])
    answers, refused = aa.parse_decision(reply(choice="Write the tests first", tier="likely", confidence=0.9,
                                               references=[]), [c], aa.KIND_CONTINUATION)
    assert refused == {} and answers["Q1"].choice == "Write the tests first"


def test_multi_select_needs_options_from_the_list():
    m = q(options=["A", "B", "C"], multi=True)
    ok, _ = aa.parse_decision(reply(choice=["A", "C"]), [m], aa.KIND_ASK)
    assert ok["Q1"].choice == "A, C"
    no, refused = aa.parse_decision(reply(choice=["A", "Z"]), [m], aa.KIND_ASK)
    assert no == {} and refused["Q1"] == "not a valid choice"


def test_one_bad_answer_does_not_sink_the_other():
    raw = json.dumps({"answers": [
        {"key": "Q1", "choice": "TEAL", "tier": "likely", "confidence": 0.9},
        {"key": "Q2", "choice": "nope", "tier": "likely", "confidence": 0.9}]})
    answers, refused = aa.parse_decision(raw, [q(), q("Q2", options=["yes", "no"])], aa.KIND_ASK)
    assert set(answers) == {"Q1"} and refused == {"Q2": "choice outside the options"}


# --------------------------------------------------------------------------- 2.3

@pytest.mark.parametrize("text,family", [
    ("May I push the 11 commits?", "publish"),
    ("Mehet a push?", "publish"),
    ("Pusholjam?", "publish"),
    ("Publish the page now?", "publish"),
    ("Cut the release now?", "publish"),
    ("Release the fix today?", "publish"),
    ("Ship it?", "publish"),
    ("Deploy to staging?", "deploy"),
    ("Élesítsük a javítást?", "deploy"),
    ("Run it against production?", "production"),
    ("Futtassam élesben?", "production"),
    ("Send the summary to the client?", "send"),
    ("Küldjem el a levelet?", "send"),
    ("Email the report?", "send"),
    ("Delete the old branch?", "delete"),
    ("Töröljem a régi ágat?", "delete"),
    ("drop table orders?", "delete"),
    ("Pay the invoice?", "pay"),
    ("Fizessük ki?", "pay"),
    ("Rotate the API key?", "credential"),
    ("Change the password?", "credential"),
    ("Add meg a jelszót?", "credential"),
])
def test_each_family_fires(text, family):
    assert family in aa.outward_hits([text])


@pytest.mark.parametrize("text", [
    "Which products page should we start with?",   # prod / production
    "Is the payload size right?",                   # pay
    "Is the repayment-free plan fine?",             # pay inside a word
    "Which tokenizer?",                             # token is not a credential on its own
    "Which release colour should the banner use?",  # about a release, not releasing
    "Use the elegant layout?",                      # eles (élesít) as a substring
    "Keep the products and the prodigy tests?",
])
def test_a_substring_of_a_pattern_word_does_not_fire(text):
    assert aa.outward_hits([text]) == []


def test_never_patterns_extend_and_a_broken_one_is_literal():
    assert aa.outward_hits(["Generate the szállítólevél?"], ["szallitolevel"]) == ["never_patterns"]
    assert aa.outward_hits(["open (paren"], ["(paren"]) == ["never_patterns"]


def test_exclusion_sides():
    plain = q(text="Which colour?", options=["TEAL", "ORANGE"])
    assert aa.exclusion(aa.KIND_PERMISSION, plain, "Allow", False) == "permission prompt"
    assert aa.exclusion(aa.KIND_ASK, plain, "TEAL", False) is None
    # AC-9: the model says not outward, the question mentions deploying
    assert aa.exclusion(aa.KIND_ASK, q(text="Deploy now?", options=["Yes", "No"]), "Yes", False)
    # the model's flag alone excludes
    assert aa.exclusion(aa.KIND_ASK, plain, "TEAL", True) == "outward step: flagged by the model"
    # an OPTION alone is enough: the step is on the table even if another one is chosen
    assert aa.exclusion(aa.KIND_ASK, q(text="How do we go on?", options=["Push to main", "Keep it local"]),
                        "Keep it local", False) == "outward step: publish"
    # the CHOSEN answer is checked too
    assert aa.exclusion(aa.KIND_CONTINUATION, q(text="Next?", options=[]), "push it", False)


# --------------------------------------------------------------------------- 2.4

@pytest.mark.parametrize("tier,conf,excluded,outcome", [
    ("decided", 0.0, None, "allowed"),
    ("found", 0.1, None, "allowed"),
    ("likely", 0.8, None, "allowed"),
    ("likely", 0.79, None, "below-bar"),
    ("likely", 0.0, None, "below-bar"),
    ("decided", 1.0, "permission prompt", "excluded"),
    ("found", 1.0, "outward step: publish", "excluded"),
    ("likely", 1.0, "outward step: flagged by the model", "excluded"),
    ("", 1.0, None, "below-bar"),
])
def test_allow_table(tier, conf, excluded, outcome):
    assert aa.allow(tier, conf, excluded, 0.8) == outcome


# --------------------------------------------------------------------------- 2.5a

def kb_run(stdout="", code=0, exc=None):
    seen = {}

    def run(argv, **kw):
        seen["argv"], seen["cwd"] = argv, kw.get("cwd")
        if exc:
            raise exc
        return SimpleNamespace(returncode=code, stdout=stdout)
    return run, seen


def test_kb_hits_reach_the_candidates(monkeypatch):
    monkeypatch.setattr(aa.shutil, "which", lambda n: "/bin/set-kb")
    run, seen = kb_run(json.dumps({"hits": [{"path": "docs/colours.md", "headingPath": "Release > Colour",
                                             "snippet": "The release colour is TEAL."}]}))
    hits, note = aa.kb_candidates([q()], "/proj", run=run)
    assert hits == [{"path": "docs/colours.md", "heading": "Release > Colour", "excerpt": "The release colour is TEAL."}]
    assert note == "kb: 1 hit(s)" and seen["cwd"] == "/proj"
    assert seen["argv"][:4] == ["/bin/set-kb", "search", "--json", "--limit"]
    assert "TEAL" in seen["argv"][-1] and "Which release colour?" in seen["argv"][-1]
    prompt = aa.build_prompt(aa.KIND_ASK, [q()], hits, [])
    assert "docs/colours.md" in prompt and "The release colour is TEAL." in prompt


@pytest.mark.parametrize("run_args,why", [
    ({"code": 2}, "exit 2"),
    ({"stdout": "<html>"}, "no hits list"),
    ({"exc": subprocess.TimeoutExpired("set-kb", 30)}, "timed out"),
    ({"exc": OSError("x")}, "OSError"),
])
def test_kb_failure_is_noted_not_fatal(monkeypatch, run_args, why):
    monkeypatch.setattr(aa.shutil, "which", lambda n: "/bin/set-kb")
    run, _ = kb_run(**run_args)
    hits, note = aa.kb_candidates([q()], "/proj", run=run)
    assert hits == [] and note.startswith("kb: not used") and why in note


def test_kb_missing_binary(monkeypatch):
    monkeypatch.setattr(aa.shutil, "which", lambda n: None)
    assert aa.kb_candidates([q()], "/proj") == ([], "kb: not used (set-kb not on PATH)")


# --------------------------------------------------------------------------- 2.5: the launch

class Plan:
    def __init__(self, provider, model, env=None, args=()):
        self.provider, self.model, self.env, self.unset, self.args = provider, model, env or {}, ("ANTHROPIC_API_KEY",), args

    def launch_args(self, caller):
        add = list(self.args)
        if "--model" not in caller:
            add += ["--model", self.model]
        return tuple(add)


def write_transcript(path: Path, entries):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("".join(json.dumps(e) + "\n" for e in entries), encoding="utf-8")
    return path


def iso(epoch):
    return datetime.fromtimestamp(epoch, tz=timezone.utc).isoformat().replace("+00:00", "Z")


def assistant(model, at=ASKED - 10):
    return {"type": "assistant", "timestamp": iso(at), "message": {"model": model, "content": [{"type": "text", "text": "ok"}]}}


def user(text, at=ASKED - 20, meta=False):
    e = {"type": "user", "timestamp": iso(at), "message": {"role": "user", "content": text}}
    if meta:
        e["isMeta"] = True
    return e


def test_an_inherited_unit_record_does_not_override_the_measured_model(tmp_path):
    """Measured live (5.2): a haiku session in a tmux server inside an Opus agent's scope
    was forked on Opus, because the unit's record belonged to the OTHER agent."""
    t = write_transcript(tmp_path / "t.jsonl", [assistant("claude-haiku-5-5")])
    launch = aa.session_launch(SID, t, pid_of=lambda s: 4242, unit=lambda p: "set-agent-other.scope",
                               record_get=lambda u: {"provider": "glm", "model": "glm-4.6"},
                               resolve=lambda **k: pytest.fail("the record's provider must not be resolved"),
                               catalogue=lambda: {"providers": [{"name": "glm", "models": ["glm-4.6"]}]})
    assert launch.argv == ["claude", "--model", "claude-haiku-5-5"] and launch.source == "transcript"
    same = aa.session_launch(SID, t, pid_of=lambda s: 4242, unit=lambda p: "set-agent-other.scope",
                             record_get=lambda u: {"provider": "anthropic", "model": "opus"},
                             resolve=lambda provider=None, model=None: Plan(provider, "opus"),
                             catalogue=lambda: {"providers": []})
    assert same.argv == ["claude", "--model", "claude-haiku-5-5"], "the record's provider, the measured model"


def test_without_a_measured_model_the_record_is_used(tmp_path):
    t = write_transcript(tmp_path / "t.jsonl", [user("hello")])
    launch = aa.session_launch(SID, t, pid_of=lambda s: 4242, unit=lambda p: "u.scope",
                               record_get=lambda u: {"provider": "glm", "model": "glm-4.6"},
                               resolve=lambda provider=None, model=None: Plan(provider, model, env={"X": "1"}),
                               catalogue=lambda: {"providers": []})
    assert launch.argv == ["claude", "--model", "glm-4.6"] and launch.source == "record"


def test_launch_from_the_fleet_record_wins(tmp_path):
    t = write_transcript(tmp_path / "t.jsonl", [assistant("glm-4.6")])
    seen = {}

    def resolve(provider=None, model=None):
        seen["args"] = (provider, model)
        return Plan(provider, model, env={"ANTHROPIC_BASE_URL": "https://glm.example"})
    launch = aa.session_launch(SID, t, pid_of=lambda s: 4242, unit=lambda p: "set-agent-a1.scope",
                               record_get=lambda u: {"provider": "glm", "model": "glm-4.6"} if u == "set-agent-a1.scope" else None,
                               resolve=resolve, catalogue=lambda: {"providers": [{"name": "glm", "models": ["glm-4.6"]}]})
    assert seen["args"] == ("glm", "glm-4.6") and launch.source == "record"
    assert launch.argv == ["claude", "--model", "glm-4.6"] and launch.env == {"ANTHROPIC_BASE_URL": "https://glm.example"}
    assert launch.unset == ("ANTHROPIC_API_KEY",)


def test_launch_from_the_transcript_model(tmp_path):
    t = write_transcript(tmp_path / "t.jsonl", [assistant("claude-opus-5-5", ASKED - 30), assistant("claude-haiku-5-5")])
    launch = aa.session_launch(SID, t, pid_of=lambda s: None, record_get=lambda u: None,
                               resolve=lambda **k: pytest.fail("no resolve for the CLI's own login"),
                               catalogue=lambda: {"providers": []})
    assert launch.argv == ["claude", "--model", "claude-haiku-5-5"] and launch.env == {}


def test_a_glm_session_forks_on_the_glm_plan(tmp_path):
    """The same plan `set-glm` resolves: its env, and the session's own measured model."""
    from set_orch.providers import UnknownModel
    t = write_transcript(tmp_path / "t.jsonl", [assistant("glm-5.3-flash")])
    calls = []

    def resolve(provider=None, model=None):
        calls.append((provider, model))
        return Plan(provider, model or "glm-4.6", env={"ANTHROPIC_BASE_URL": "https://z"})
    launch = aa.session_launch(SID, t, pid_of=lambda s: None, record_get=lambda u: None, resolve=resolve,
                               catalogue=lambda: {"providers": [{"name": "anthropic", "models": ["opus"]},
                                                                {"name": "glm", "models": ["glm-5.3-flash"]}]})
    assert calls == [("glm", "glm-5.3-flash")] and launch.provider == "glm"
    assert launch.argv == ["claude", "--model", "glm-5.3-flash"] and launch.env["ANTHROPIC_BASE_URL"] == "https://z"

    def strict(provider=None, model=None):
        if model:
            raise UnknownModel("no")
        return Plan(provider, "glm-4.6", env={"ANTHROPIC_BASE_URL": "https://z"})
    launch = aa.session_launch(SID, t, pid_of=lambda s: None, record_get=lambda u: None, resolve=strict,
                               catalogue=lambda: {"providers": [{"name": "glm", "models": ["glm-5.3-flash"]}]})
    assert launch.argv == ["claude", "--model", "glm-5.3-flash"], "the session's model wins over the default"


def test_an_unplaceable_model_is_not_forked_on_a_guess(tmp_path):
    t = write_transcript(tmp_path / "t.jsonl", [assistant("mystery-1")])
    assert aa.session_launch(SID, t, pid_of=lambda s: None, record_get=lambda u: None,
                             catalogue=lambda: {"providers": []}) is None


def test_auto_answer_model_never_reaches_a_fork():
    """AC-6e: `auto_answer.model` applies to the fallback only."""
    launch = aa.Launch(argv=["claude", "--model", "claude-haiku-5-5"], env={}, unset=(), provider="anthropic",
                       model="claude-haiku-5-5", source="transcript")
    argv = aa.fork_argv(launch, SID)
    assert argv.count("--model") == 1 and argv[argv.index("--model") + 1] == "claude-haiku-5-5"
    assert ["--resume", SID] == argv[argv.index("--resume"):argv.index("--resume") + 2]
    for flag in ("--fork-session", "--no-session-persistence", "--strict-mcp-config", "-p"):
        assert flag in argv
    assert argv[argv.index("--tools") + 1] == "Read,Grep,Glob"
    fb = aa.fallback_argv("sonnet")
    assert "--fork-session" not in fb and "--resume" not in fb and fb[fb.index("--model") + 1] == "sonnet"


# --------------------------------------------------------------------------- 2.5 / 3.4b: real processes

def fake_claude(tmp_path: Path, body: str) -> Path:
    bindir = tmp_path / "bin"
    bindir.mkdir(exist_ok=True)
    exe = bindir / "claude"
    exe.write_text(f"#!{sys.executable}\nimport json, os, subprocess, sys, time\n{body}\n")
    exe.chmod(0o755)
    return bindir


def test_fork_runs_with_its_argv_and_guard(tmp_path, monkeypatch):
    record = tmp_path / "argv.json"
    bindir = fake_claude(tmp_path, f"""
json.dump({{"argv": sys.argv[1:], "guard": os.environ.get("{aa.GUARD_ENV}"),
           "unset": "ANTHROPIC_API_KEY" in os.environ, "base": os.environ.get("ANTHROPIC_BASE_URL"),
           "stdin": sys.stdin.read()}}, open({str(record)!r}, "w"))
print(json.dumps({{"result": "{{}}", "usage": {{"cache_read_input_tokens": 9}}}}))""")
    monkeypatch.setenv("PATH", f"{bindir}{os.pathsep}{os.environ['PATH']}")
    monkeypatch.setenv("ANTHROPIC_API_KEY", "should-be-removed")
    launch = aa.Launch(argv=["claude", "--model", "glm-5.3-flash"], env={"ANTHROPIC_BASE_URL": "https://z"},
                       unset=("ANTHROPIC_API_KEY",), provider="glm", model="glm-5.3-flash", source="record")
    out, reason = aa.run_bounded(aa.fork_argv(launch, SID), "PROMPT", cwd=str(tmp_path), env=launch.env,
                                 unset=launch.unset, timeout=20)
    seen = json.loads(record.read_text())
    assert reason == "ok" and aa.result_text(out)[1]["cache_read_input_tokens"] == 9
    assert "--fork-session" in seen["argv"] and SID in seen["argv"] and "glm-5.3-flash" in seen["argv"]
    assert seen["guard"] == "1" and seen["unset"] is False and seen["base"] == "https://z"
    assert seen["stdin"] == "PROMPT"


def test_non_zero_exit_is_no_decision(tmp_path, monkeypatch):
    bindir = fake_claude(tmp_path, "sys.exit(3)")
    monkeypatch.setenv("PATH", f"{bindir}{os.pathsep}{os.environ['PATH']}")
    assert aa.run_bounded(["claude", "-p"], "x", cwd=str(tmp_path), env={}, timeout=20) == (None, "exited 3")


def _alive(pids):
    alive = []
    for pid in pids:
        try:
            os.kill(pid, 0)
        except ProcessLookupError:
            continue
        # a zombie is not alive: it holds no resources and runs nothing
        try:
            state = Path(f"/proc/{pid}/stat").read_text().split(")")[-1].split()[0]
        except OSError:
            continue
        if state != "Z":
            alive.append(pid)
    return alive


def test_the_bound_kills_the_whole_group(tmp_path, monkeypatch):
    """3.4b / AC-15: a fork that spawned a child and hangs leaves nothing alive after its bound."""
    pids = tmp_path / "pids"
    bindir = fake_claude(tmp_path, f"""
child = subprocess.Popen([sys.executable, "-c", "import time; time.sleep(120)"])
open({str(pids)!r}, "w").write(f"{{os.getpid()}} {{child.pid}}")
time.sleep(120)""")
    monkeypatch.setenv("PATH", f"{bindir}{os.pathsep}{os.environ['PATH']}")
    t0 = time.monotonic()
    out, reason = aa.run_bounded(["claude", "-p"], "x", cwd=str(tmp_path), env={}, timeout=2)
    assert out is None and reason.startswith("timed out") and time.monotonic() - t0 < 15
    both = [int(p) for p in pids.read_text().split()]
    assert len(both) == 2 and _alive(both) == []


def test_a_child_left_after_a_normal_exit_is_swept(tmp_path, monkeypatch):
    """AC-14: the fork answered and exited, but a child it started is still the fork's."""
    pids = tmp_path / "pids"
    bindir = fake_claude(tmp_path, f"""
child = subprocess.Popen([sys.executable, "-c", "import time; time.sleep(120)"])
open({str(pids)!r}, "w").write(str(child.pid))
print("{{}}")""")
    monkeypatch.setenv("PATH", f"{bindir}{os.pathsep}{os.environ['PATH']}")
    out, reason = aa.run_bounded(["claude", "-p"], "x", cwd=str(tmp_path), env={}, timeout=20)
    assert reason == "ok"
    time.sleep(0.3)
    assert _alive([int(pids.read_text())]) == []


# --------------------------------------------------------------------------- 2.5b

def answer_with(*refs, tier="decided", conf=0.9):
    return aa.Answer(key="Q1", choice="TEAL", claimed_tier=tier, confidence=conf, outward=False, references=list(refs))


def test_operator_quote_checks_out(tmp_path):
    t = write_transcript(tmp_path / "t.jsonl", [user("I decided: the release color is TEAL, not orange.")])
    a = aa.check_references(answer_with(aa.Reference("operator", "the release color   is TEAL")),
                            aa.operator_turns(t, ASKED), str(tmp_path))
    assert a.tier == "decided" and a.references[0].checked is True


@pytest.mark.parametrize("entries", [
    # the words are the AGENT's, not the operator's
    [{"type": "assistant", "timestamp": iso(ASKED - 5),
      "message": {"content": [{"type": "text", "text": "the release color is TEAL"}]}}],
    # the operator said it, but only AFTER the question
    [user("the release color is TEAL", at=ASKED + 5)],
    # injected by the harness, not said by the operator
    [user("<system-reminder>the release color is TEAL</system-reminder>")],
    [user("the release color is TEAL", meta=True)],
    [user("<task-notification> the release color is TEAL")],
    # a tool result is not a turn
    [{"type": "user", "timestamp": iso(ASKED - 5),
      "message": {"content": [{"type": "tool_result", "content": "the release color is TEAL"}]}}],
])
def test_operator_quote_that_does_not_count(tmp_path, entries):
    """AC-4a: a quote that does not check out drops the tier to likely."""
    t = write_transcript(tmp_path / "t.jsonl", entries)
    a = aa.check_references(answer_with(aa.Reference("operator", "the release color is TEAL")),
                            aa.operator_turns(t, ASKED), str(tmp_path))
    assert a.tier == "likely" and a.references[0].checked is False
    assert aa.allow(a.tier, a.confidence, None, 0.95) == "below-bar"


def test_file_excerpt_found_and_decision_record(tmp_path):
    (tmp_path / "docs").mkdir()
    (tmp_path / "docs" / "release.md").write_text("# Release\n\nThe release colour   is\nTEAL from now on.\n")
    a = aa.check_references(answer_with(aa.Reference("file", "The release colour is TEAL", path="docs/release.md"),
                                        tier="found"), [], str(tmp_path))
    assert a.tier == "found" and a.references[0].checked
    d = aa.check_references(answer_with(aa.Reference("file", "The release colour is TEAL", path="docs/release.md",
                                                     decision=True)), [], str(tmp_path))
    assert d.tier == "decided"


@pytest.mark.parametrize("ref", [
    aa.Reference("file", "The release colour is PURPLE", path="docs/release.md"),
    aa.Reference("file", "The release colour is TEAL", path="docs/missing.md"),
    aa.Reference("file", "TEAL", path="docs/release.md"),          # too short to prove anything
    aa.Reference("operator", "TEAL"),
])
def test_references_that_fail(tmp_path, ref):
    (tmp_path / "docs").mkdir()
    (tmp_path / "docs" / "release.md").write_text("The release colour is TEAL.\n")
    a = aa.check_references(answer_with(ref, tier="found"), ["teal is what TEAL means"], str(tmp_path))
    assert a.tier == "likely" and ref.checked is False and ref.reason


# --------------------------------------------------------------------------- the whole decision

def run_decide(tmp_path, out, *, launch=True, kb=None, transcript_entries=None, envelope=None, reason="ok"):
    t = write_transcript(tmp_path / f"{SID}.jsonl", transcript_entries or
                         [user("I decided: the release color is TEAL, not orange."), assistant("claude-haiku-5-5")])
    seen = {}

    def runner(argv, prompt, **kw):
        seen["argv"], seen["prompt"], seen["kw"] = argv, prompt, kw
        return (out, reason) if out is not None else (None, reason)
    lnch = aa.Launch(argv=["claude", "--model", "claude-haiku-5-5"], env={}, unset=(), provider="anthropic",
                     model="claude-haiku-5-5", source="transcript")
    d = aa.decide(envelope or env_of(q()), kind=aa.KIND_ASK, session_id=SID, cwd=str(tmp_path), asked_at=ASKED,
                  get=cfg(**{aa.KEY_MODEL: "claude-fable-5-2"}),
                  kb=kb or (lambda qs, cwd: ([], "kb: not used (exit 2)")),
                  launch_of=lambda s, p: lnch if launch else None,
                  transcript=lambda s: t, runner=runner)
    return d, seen


def test_decide_by_fork_checks_the_quote(tmp_path):
    """AC-6c: the operator's own words, quoted and checked."""
    d, seen = run_decide(tmp_path, json.dumps({"result": reply(), "usage": {"cache_read_input_tokens": 5}}))
    assert d.method == "fork" and d.answers["Q1"].tier == "decided" and d.answers["Q1"].references[0].checked
    assert "--fork-session" in seen["argv"] and "claude-fable-5-2" not in seen["argv"]
    assert "kb: not used (exit 2)" in d.notes, "AC-6b: the log says the kb was not used"


def test_decide_with_a_fabricated_quote_is_likely(tmp_path):
    d, _ = run_decide(tmp_path, reply(references=[{"kind": "operator", "quote": "I always want TEAL releases"}],
                                      confidence=0.5))
    assert d.answers["Q1"].tier == "likely"
    assert aa.allow(d.answers["Q1"].tier, d.answers["Q1"].confidence, None, 0.8) == "below-bar"


def test_decide_kb_hit_reaches_the_fork_and_found_names_it(tmp_path):
    """AC-6a."""
    (tmp_path / "docs").mkdir()
    (tmp_path / "docs" / "meeting-notes.md").write_text("Agreed in the meeting: releases ship in TEAL.\n")
    out = reply(tier="found", references=[{"kind": "file", "path": "docs/meeting-notes.md",
                                           "quote": "releases ship in TEAL"}])
    d, seen = run_decide(tmp_path, out, kb=lambda qs, cwd: ([{"path": "docs/meeting-notes.md", "heading": "Meeting",
                                                              "excerpt": "releases ship in TEAL"}], "kb: 1 hit(s)"))
    assert "docs/meeting-notes.md" in seen["prompt"]
    assert d.answers["Q1"].tier == "found" and d.answers["Q1"].references[0].path == "docs/meeting-notes.md"


def test_decide_timeout_is_no_decision(tmp_path):
    """AC-6."""
    d, _ = run_decide(tmp_path, None, reason="timed out after 120 s")
    assert d.answers == {} and d.refused == {"Q1": "timed out after 120 s"}


def test_decide_outside_the_options_is_no_decision(tmp_path):
    """AC-5."""
    d, _ = run_decide(tmp_path, reply(choice="PURPLE"))
    assert d.answers == {} and d.refused["Q1"] == "choice outside the options"


def test_an_unresumable_session_falls_back(tmp_path):
    d, seen = run_decide(tmp_path, reply(tier="likely", confidence=0.9, references=[]), launch=False)
    assert d.method == "fallback" and "--fork-session" not in seen["argv"]
    assert seen["argv"][seen["argv"].index("--model") + 1] == "claude-fable-5-2"
    assert any(n.startswith("fallback: sources-only") for n in d.notes)
    assert "NOT a fork" in seen["prompt"]


def test_decision_locations_point_where_decisions_live(tmp_path):
    root = tmp_path / "proj"
    for rel in (".claude/rules", "openspec/changes/one", "openspec/changes/archive", "openspec/bugs", ".set/handoff"):
        (root / rel).mkdir(parents=True)
    (root / "CLAUDE.md").write_text("x")
    (root / "openspec/bugs/README.md").write_text("x")
    old, new = root / ".set/handoff/1-a.md", root / ".set/handoff/2-b.md"
    old.write_text("x")
    new.write_text("x")
    os.utime(old, (1, 1))
    (root / "docs").mkdir()
    (root / "docs/decisions.md").write_text("x")
    locs = aa.decision_locations(str(root), ["docs/decisions.md", "nope.md"], home=tmp_path / "home")
    assert str(root / "CLAUDE.md") in locs and str(root / ".claude/rules") in locs
    assert str(new) in locs and str(old) not in locs, "only the newest handoff"
    assert str(root / "openspec/changes/one") in locs and str(root / "openspec/changes/archive") not in locs
    assert str(root / "docs/decisions.md") in locs and not any("nope" in l for l in locs)
