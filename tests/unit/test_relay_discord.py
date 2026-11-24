"""relay-discord-bridge: the answer rules, the post/poll/notify commands and setup.

No network: a fake Discord holds messages, reactions and replies in memory; the config is a
dict. The relay's state dir is a tmp dir, so the answer files and post records are real files.
"""
from __future__ import annotations

import argparse
import io
import json
import logging
import os
import stat
from pathlib import Path

import pytest

from set_orch.fleet import relay_discord as rd

CHANNEL, ME, BOT, STRANGER = "1111111111", "2222222222", "9999999999", "3333333333"
NOW = 1_800_000_000.0
QUESTION = "Should the zebra-banner-7Q ship today?"


class Store(dict):
    """A dict that is also called like `local_config.get`, and written like `set_value`."""

    def __call__(self, key, project=None, default=None):
        return dict.get(self, key, default)

    def set_value(self, key, value, project=None):
        self[key] = value


def config(**over):
    s = Store({rd.KEY_CHANNEL: CHANNEL, rd.KEY_ALLOWED: json.dumps([ME]), rd.KEY_BOT_ID: BOT})
    s.update(over)
    return s


class FakeDiscord(rd.Discord):
    def __init__(self, fail_after=None):
        super().__init__("t")
        self.next_id, self.messages, self.reactions, self.sent = 5_000_000_000, {}, {}, []
        self.fail_after = fail_after
        self.gone = set()

    def _new(self, channel, content, ref=None, author=BOT):
        self.next_id += 1
        mid = str(self.next_id)
        self.messages[mid] = {"id": mid, "content": content, "author": {"id": author},
                              **({"message_reference": {"message_id": ref}} if ref else {})}
        return self.messages[mid]

    def send(self, channel_id, content, reply_to=None):
        if self.fail_after is not None and len(self.sent) >= self.fail_after:
            raise rd.DiscordError(503, "POST /channels/<id>/messages")
        self.sent.append((content, reply_to))
        return self._new(channel_id, content, reply_to)

    def react(self, channel_id, message_id, emoji):
        self.reactions.setdefault(message_id, {}).setdefault(emoji, [])
        if BOT not in self.reactions[message_id][emoji]:
            self.reactions[message_id][emoji].append(BOT)

    def user_reacts(self, message_id, emoji, user=ME):
        self.reactions.setdefault(message_id, {}).setdefault(emoji, []).append(user)

    def user_replies(self, message_id, text, user=ME):
        return self._new(CHANNEL, text, message_id, author=user)

    def message(self, channel_id, message_id):
        if message_id in self.gone:
            raise rd.DiscordError(404, "GET")
        m = dict(self.messages[message_id])
        m["reactions"] = [{"emoji": {"name": e}, "count": len(us), "me": BOT in us}
                          for e, us in self.reactions.get(message_id, {}).items()]
        return m

    def reactors(self, channel_id, message_id, emoji):
        return list(self.reactions.get(message_id, {}).get(emoji, []))

    def messages_after(self, channel_id, after, pages=rd.REPLY_PAGES):
        return [m for k, m in sorted(self.messages.items(), key=lambda kv: int(kv[0])) if int(k) > int(after)]

    def me(self):
        return {"id": BOT, "username": "relay-bot"}

    def channel(self, channel_id):
        return {"id": channel_id}


def envelope(tmp_path, options=("Yes", "No"), multi=False, n=1):
    return json.dumps({"questions": [{
        "id": "relay-abcd1234-0000beef", "key": f"Q{i}", "question": QUESTION,
        "optionsList": list(options), "multi": multi, "audience": "DEV",
        "source": "demo-project · abcd1234", "valasz_tar": str(tmp_path / "answers")}
        for i in range(1, n + 1)]})


def world(tmp_path, d=None, get=None, now=NOW):
    return rd.World(get=get if get is not None else config(), client=d or FakeDiscord(), base=tmp_path, now=lambda: now)


def waiting(tmp_path, cid="relay-abcd1234-0000beef"):
    (tmp_path / "waiting").mkdir(exist_ok=True)
    (tmp_path / "waiting" / "abcd1234-sess.json").write_text(json.dumps({"id": cid}))


def posted(tmp_path, **kw):
    d = FakeDiscord()
    w = world(tmp_path, d)
    assert rd.post(envelope(tmp_path, **kw), "ask", w) == 0
    rec = rd.load_records(tmp_path)[0]
    return d, w, rec


# ----------------------------------------------------------------------------- the rules

def test_one_reaction_answers_a_single_question():
    """AC-5."""
    v = rd.decide(["Yes", "No"], False, {"2️⃣": [BOT, ME]}, [], [ME], BOT)
    assert (v.state, v.text) == ("answer", "No")


def test_a_numbered_reply_with_a_note():
    """AC-6."""
    v = rd.decide(["Yes", "No"], False, {}, [{"author": ME, "text": "1, but only after the review"}], [ME])
    assert (v.state, v.text) == ("answer", "Yes — but only after the review")


def test_free_text_is_verbatim_and_a_year_is_not_an_option_number():
    """AC-7."""
    for text in ("Neither: wait for the design call", "2026-tól mehet", "7 is not an option"):
        v = rd.decide(["Yes", "No"], False, {}, [{"author": ME, "text": text}], [ME])
        assert (v.state, v.text) == ("answer", text)


def test_the_last_reply_wins():
    v = rd.decide(["Yes", "No"], False, {"1️⃣": [ME]},
                  [{"author": ME, "text": "1"}, {"author": ME, "text": "No, later"}], [ME])
    assert v.text == "No, later"


def test_multi_select_waits_for_the_tick():
    """AC-8."""
    opts = ["A", "B", "C"]
    assert rd.decide(opts, True, {"1️⃣": [ME], "3️⃣": [ME]}, [], [ME]).state == "wait"
    v = rd.decide(opts, True, {"1️⃣": [ME], "3️⃣": [ME], "✅": [ME]}, [{"author": ME, "text": "and D"}], [ME])
    assert (v.state, v.text) == ("answer", "A · C · and D")
    assert rd.decide(opts, True, {"✅": [ME]}, [], [ME]).state == "unclear"


def test_two_reactions_on_a_single_question_are_not_an_answer():
    """AC-9."""
    assert rd.decide(["Yes", "No"], False, {"1️⃣": [ME], "2️⃣": [ME]}, [], [ME]).state == "unclear"


def test_a_stranger_and_the_bot_do_not_count():
    """AC-4."""
    assert rd.decide(["Yes", "No"], False, {"1️⃣": [STRANGER, BOT]},
                     [{"author": STRANGER, "text": "Yes"}], [ME], BOT).state == "wait"


def test_the_cross_defers_everything():
    assert rd.decide(["Yes", "No"], False, {"1️⃣": [ME], "❌": [ME]},
                     [{"author": ME, "text": "1"}], [ME]).state == "defer"


def test_message_text_numbers_the_options_and_stays_under_the_limit():
    e = json.loads(envelope(Path("/tmp"), options=[f"opt{i}" for i in range(7)]))["questions"][0]
    e["question"] = "x" * 5000
    text = rd.message_text(e, "permission")
    assert len(text) <= rd.MESSAGE_LIMIT and "permission prompt" in text and "demo-project" in text
    assert "1️⃣ opt0" in text and "5️⃣ opt4" in text and "6. opt5" in text and "7. opt6" in text


# ----------------------------------------------------------------------------- post / notify

def test_a_two_option_question_is_posted(tmp_path):
    """AC-1."""
    d, _, rec = posted(tmp_path)
    content, ref = d.sent[0]
    assert QUESTION in content and "question" in content and "1️⃣ Yes" in content and ref is None
    assert set(d.reactions[rec["message_id"]]) == {"1️⃣", "2️⃣", "❌"}
    assert rec["state"] == "open" and rec["options"] == ["Yes", "No"]
    assert stat.S_IMODE(os.stat(rd.record_path(rec["id"], rec["key"], tmp_path)).st_mode) == 0o600


def test_a_multi_select_post_gets_the_tick(tmp_path):
    d, _, rec = posted(tmp_path, options=("A", "B"), multi=True)
    assert "✅" in d.reactions[rec["message_id"]]


def test_discord_unreachable_means_non_zero_and_no_record_for_the_failed_question(tmp_path, caplog):
    """AC-2."""
    w = world(tmp_path, FakeDiscord(fail_after=1))
    with caplog.at_level(logging.INFO):
        assert rd.post(envelope(tmp_path, n=2), "ask", w) == 3
    assert [r["key"] for r in rd.load_records(tmp_path)] == ["Q1"]
    assert "Q2" in caplog.text and "503" in caplog.text and QUESTION not in caplog.text


@pytest.mark.parametrize("gap", [rd.KEY_CHANNEL, rd.KEY_ALLOWED])
def test_not_configured_posts_nothing_and_names_the_gap(tmp_path, capsys, gap):
    """AC-3."""
    get = config(**{gap: ""})
    d = FakeDiscord()
    assert rd.post(envelope(tmp_path), "ask", world(tmp_path, d, get)) == 2
    assert d.sent == [] and gap in capsys.readouterr().err


def test_a_missing_token_is_named(tmp_path, monkeypatch):
    monkeypatch.setattr(rd, "token_path", lambda: tmp_path / "none.token")
    assert any("token" in g for g in rd.missing(config()))


def test_notify_posts_one_plain_message(tmp_path):
    """AC-17."""
    d = FakeDiscord()
    env = json.dumps({"kind": "notification", "agent": "demo-project · abcd1234", "message": "needs you"})
    assert rd.notify(env, world(tmp_path, d)) == 0
    assert len(d.sent) == 1 and "demo-project · abcd1234" in d.sent[0][0] and d.reactions == {}


# ----------------------------------------------------------------------------- poll

def test_an_allowed_reaction_writes_the_answer_and_acknowledges(tmp_path):
    """AC-10."""
    d, w, rec = posted(tmp_path)
    waiting(tmp_path)
    d.user_reacts(rec["message_id"], "1️⃣")
    assert rd.poll(w) == {"answered": 1}
    path = rd.answer_path(rec)
    assert json.loads(path.read_text()) == {"valasz": "Yes"}
    assert stat.S_IMODE(os.stat(path).st_mode) == 0o600
    assert rd.RECORDED in d.reactions[rec["message_id"]]
    assert d.sent[-1][1] == rec["message_id"] and "Yes" in d.sent[-1][0]
    assert rd.load_records(tmp_path)[0]["state"] == "answered"
    assert rd.poll(w) == {}, "an answered post is never written again"


def test_a_stranger_reaction_writes_nothing(tmp_path):
    d, w, rec = posted(tmp_path)
    waiting(tmp_path)
    d.user_reacts(rec["message_id"], "1️⃣", user=STRANGER)
    assert rd.poll(w) == {"wait": 1} and not rd.answer_path(rec).exists()


def test_the_fleet_answered_first(tmp_path):
    """AC-11."""
    d, w, rec = posted(tmp_path)
    waiting(tmp_path)
    rd.answer_path(rec).parent.mkdir(parents=True, exist_ok=True)
    rd.answer_path(rec).write_text(json.dumps({"valasz": "from the fleet"}))
    d.user_reacts(rec["message_id"], "2️⃣")
    assert rd.poll(w) == {"answered-elsewhere": 1}
    assert json.loads(rd.answer_path(rec).read_text()) == {"valasz": "from the fleet"}
    assert "elsewhere" in d.sent[-1][0]


def test_answered_at_the_terminal_closes_after_the_grace(tmp_path):
    """AC-12."""
    d, _, rec = posted(tmp_path)
    (tmp_path / "waiting").mkdir()
    assert rd.poll(world(tmp_path, d, now=NOW + 30)) == {"wait": 1}, "inside the grace it stays open"
    assert rd.poll(world(tmp_path, d, now=NOW + rd.GRACE_S + 1)) == {"closed": 1}
    assert "Closed" in d.sent[-1][0] and not rd.answer_path(rec).exists()


def test_an_unreadable_waiting_folder_closes_nothing(tmp_path):
    """AC-13."""
    d, _, rec = posted(tmp_path)
    (tmp_path / "waiting").mkdir()
    (tmp_path / "waiting" / "x.json").write_text("not json")
    assert rd.waiting_ids(tmp_path) is None
    assert rd.poll(world(tmp_path, d, now=NOW + 3600)) == {"wait": 1}


def test_a_reply_answers_and_two_reactions_are_said_once(tmp_path):
    d, w, rec = posted(tmp_path)
    waiting(tmp_path)
    d.user_reacts(rec["message_id"], "1️⃣")
    d.user_reacts(rec["message_id"], "2️⃣")
    assert rd.poll(w) == {"unclear": 1} and "Not taken" in d.sent[-1][0]
    n = len(d.sent)
    assert rd.poll(w) == {"unclear": 1} and len(d.sent) == n, "the warning is posted once"
    d.user_replies(rec["message_id"], "2, after lunch")
    assert rd.poll(w) == {"answered": 1}
    assert json.loads(rd.answer_path(rec).read_text()) == {"valasz": "No — after lunch"}


def test_a_deleted_post_is_closed(tmp_path):
    d, w, rec = posted(tmp_path)
    waiting(tmp_path)
    d.gone.add(rec["message_id"])
    assert rd.poll(w) == {"closed": 1}


def test_logs_carry_ids_never_text(tmp_path, caplog):
    """AC-16."""
    with caplog.at_level(logging.INFO, logger="set_orch"):
        d, w, rec = posted(tmp_path)
        waiting(tmp_path)
        d.user_replies(rec["message_id"], "the secret-answer-7Q")
        rd.poll(w)
    assert rec["id"] in caplog.text and "answer written" in caplog.text
    assert "zebra" not in caplog.text and "secret-answer" not in caplog.text and "Yes" not in caplog.text


def test_old_records_are_pruned(tmp_path):
    d, w, rec = posted(tmp_path)
    rd._end(rec, "closed", w)
    rd.prune(tmp_path, NOW + rd.RETENTION_S + 10)
    assert rd.load_records(tmp_path) == []


# ----------------------------------------------------------------------------- transport

def test_the_client_retries_once_on_429_and_reports_status_only(caplog):
    calls = []

    def opener(req, timeout):
        calls.append(req.full_url)
        if len(calls) == 1:
            return 429, b'{"retry_after": 0.01}', {}
        return 403, b'{"message": "Missing Access"}', {}

    client = rd.Discord("tok", opener=opener, sleep=lambda s: None)
    with pytest.raises(rd.DiscordError) as exc, caplog.at_level(logging.WARNING):
        client.channel("123456789012")
    assert exc.value.status == 403 and len(calls) == 2
    assert "123456789012" not in caplog.text and "tok" not in caplog.text


# ----------------------------------------------------------------------------- setup

def run_setup(tmp_path, get, **kw):
    args = argparse.Namespace(channel=CHANNEL, allow=[ME], token_stdin=True, replace=False, remove=False)
    for k, v in kw.items():
        setattr(args, k, v)
    out, calls = [], []
    stdin = io.StringIO("bot-token-value\n")
    old = rd.sys.stdin
    rd.sys.stdin = stdin
    try:
        code = rd.setup(args, rd.World(get=get, client=FakeDiscord(), base=tmp_path),
                        set_value=get.set_value, systemctl=lambda cmd, **k: calls.append(cmd),
                        out=out.append, token_file=tmp_path / "cfg" / rd.TOKEN_NAME, units=tmp_path / "units")
    finally:
        rd.sys.stdin = old
    return code, "\n".join(out), calls


def test_first_setup_behind_the_auto_answer(tmp_path):
    """AC-14: the relay command is the auto-answer outbound, so the bridge goes behind it."""
    get = Store({"question_relay.command": "/usr/local/bin/set-auto-answer", "question_relay.audience": "DEV"})
    code, out, calls = run_setup(tmp_path, get)
    assert code == 0, out
    token = tmp_path / "cfg" / rd.TOKEN_NAME
    assert token.read_text().strip() == "bot-token-value" and stat.S_IMODE(os.stat(token).st_mode) == 0o600
    assert get[rd.KEY_AA_FORWARD].endswith("set-relay-discord post")
    assert get["question_relay.command"] == "/usr/local/bin/set-auto-answer"
    assert get["question_relay.notify_command"].endswith("set-relay-discord notify")
    assert get[rd.KEY_CHANNEL] == CHANNEL and json.loads(get[rd.KEY_ALLOWED]) == [ME] and get[rd.KEY_BOT_ID] == BOT
    assert (tmp_path / "units" / "set-relay-discord.timer").exists()
    assert ["systemctl", "--user", "enable", "--now", "set-relay-discord.timer"] in calls
    assert "bot-token-value" not in out and "token works" in out and "can see the channel" in out


def test_first_setup_as_the_relay_command(tmp_path):
    get = Store()
    code, out, _ = run_setup(tmp_path, get)
    assert code == 0, out
    assert get["question_relay.command"].endswith("set-relay-discord post")
    assert get["question_relay.target"] == "command" and get["question_relay.audience"] == "DEV"


def test_another_bridge_is_not_replaced_without_the_flag(tmp_path):
    """AC-15."""
    get = Store({"question_relay.command": "set-auto-answer", rd.KEY_AA_FORWARD: "node other-bridge.mjs be"})
    code, out, calls = run_setup(tmp_path, get)
    assert code == 2 and get[rd.KEY_AA_FORWARD] == "node other-bridge.mjs be"
    assert "node other-bridge.mjs be" in out and "--replace" in out and calls == []
    code, out, _ = run_setup(tmp_path, get, replace=True)
    assert code == 0 and get[rd.KEY_AA_FORWARD].endswith("set-relay-discord post")
    assert json.loads(get[rd.KEY_PREVIOUS])[rd.KEY_AA_FORWARD] == "node other-bridge.mjs be"
    code, out, _ = run_setup(tmp_path, get, remove=True, token_stdin=False)
    assert code == 0 and get[rd.KEY_AA_FORWARD] == "node other-bridge.mjs be"
    assert not (tmp_path / "units" / "set-relay-discord.timer").exists()
