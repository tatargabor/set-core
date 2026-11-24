"""A two-way Discord bridge for the question relay.

OpenSpec change: relay-discord-bridge.

The relay hands every blocking point to a configured command and reads the answer back from
its answer store. This module is that command for Discord, built on the REST API alone:

- `post`   — the relay envelope on stdin → one message per question in the channel, with the
             options as number reactions; a post record per question. Exit 0 only if all landed.
- `notify` — the relay's notification envelope → one plain message.
- `poll`   — run every minute by a user timer: for each open post, the allowed users'
             reactions and replies → `decide()` → `<answer dir>/<id>__<key>.json` → an
             acknowledgement on the post. A post whose question no longer waits is closed.
- `setup` / `status` / `test` — wire one machine, report, probe.

The contract it reads (measured, unchanged by this module): the envelope
`{"questions": [{id, key, question, optionsList, multi, audience, source, valasz_tar}]}`, the
answer file `{"valasz": text}`, and `<relay state>/waiting/<session>.json` carrying `id` while the
call waits. Logs carry call ids, keys, HTTP statuses and outcomes, never a question's or an
answer's text.
"""

from __future__ import annotations

import argparse
import json
import logging
import os
import re
import shutil
import stat
import subprocess
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Tuple

from .. import local_config
from . import question_relay as qr

logger = logging.getLogger(__name__)

API = "https://discord.com/api/v10"
USER_AGENT = "DiscordBot (https://github.com/tatargabor/set-core, 1)"
HTTP_TIMEOUT_S = 15.0

KEY_CHANNEL = "relay_discord.channel_id"
KEY_ALLOWED = "relay_discord.allowed_users"
KEY_BOT_ID = "relay_discord.bot_id"
KEY_PREVIOUS = "relay_discord.previous"
KEY_AA_FORWARD = "auto_answer.forward_command"
TOKEN_NAME = "relay-discord.token"

NUMBERS = ("1️⃣", "2️⃣", "3️⃣", "4️⃣", "5️⃣")
DEFER = "❌"
CLOSE = "✅"
RECORDED = "🖥️"
GRACE_S = 120.0
RETENTION_S = 7 * 24 * 3600
MESSAGE_LIMIT = 2000
REPLY_PAGES = 10

KIND_LABELS = {"ask": "question", "permission": "permission prompt", "continuation": "what next?"}

UNIT_NAME = "set-relay-discord"

Getter = Callable[..., Any]


# --------------------------------------------------------------------------- #
# configuration
# --------------------------------------------------------------------------- #

def _text(value: Any) -> str:
    return str(value).strip() if value is not None else ""


def token_path() -> Path:
    return local_config.config_dir() / TOKEN_NAME


def read_token(path: Optional[Path] = None) -> Optional[str]:
    path = path or token_path()
    try:
        token = path.read_text(encoding="utf-8").strip()
    except OSError:
        return None
    try:
        if path.stat().st_mode & (stat.S_IRWXG | stat.S_IRWXO):
            logger.warning("relay discord: %s is readable by others; chmod 600 it", path.name)
    except OSError:
        pass
    return token or None


def allowed_users(get: Getter = local_config.get) -> List[str]:
    """A JSON list, or ids separated by commas, spaces or lines (`set-config` stores a string)."""
    raw = get(KEY_ALLOWED)
    if raw is None:
        return []
    if isinstance(raw, (list, tuple)):
        items = [_text(x) for x in raw]
    else:
        text = _text(raw)
        items = []
        if text.startswith("["):
            try:
                data = json.loads(text)
                items = [_text(x) for x in data] if isinstance(data, list) else []
            except ValueError:
                logger.warning("relay discord: %s is not a valid JSON list", KEY_ALLOWED)
        if not items:
            items = re.split(r"[\s,]+", text)
    return [i for i in items if i.isdigit()]


def missing(get: Getter = local_config.get, token: Optional[str] = None) -> List[str]:
    """What the bridge cannot work without — named, so a half-configured machine says so."""
    out = []
    if not (token if token is not None else read_token()):
        out.append(f"the bot token ({token_path()})")
    if not _text(get(KEY_CHANNEL)).isdigit():
        out.append(KEY_CHANNEL)
    if not allowed_users(get):
        out.append(KEY_ALLOWED)
    return out


# --------------------------------------------------------------------------- #
# the answer rules — pure
# --------------------------------------------------------------------------- #

@dataclass
class Verdict:
    state: str                 # "answer" | "defer" | "wait" | "unclear"
    text: str = ""
    how: str = ""


_NUMBERED = re.compile(r"^\s*([1-9])(?!\d)\s*[.,:;)—–-]?\s*(.*)$", re.S)


def decide(options: List[str], multi: bool, reactions: Dict[str, List[str]],
           replies: List[Dict[str, str]], allowed: List[str], bot_id: str = "") -> Verdict:
    """The answer to one post, from who reacted with what and who replied what.

    `reactions` maps an emoji to the user ids that added it; `replies` are the replies to the
    post in time order (`{"author": id, "text": str}`). Only allowed users count, never the bot.
    ❌ defers. Multi-select collects numbers and replies and only ✅ closes. Single-select: the
    last reply wins ("2, note" = option 2 plus the note), else exactly one number reaction.
    """
    ok = set(allowed) - ({bot_id} if bot_id else set())

    def by_allowed(emoji: str) -> bool:
        return any(u in ok for u in reactions.get(emoji, []))

    if by_allowed(DEFER):
        return Verdict("defer", how="reaction")
    chosen = [i for i, e in enumerate(NUMBERS[:len(options)]) if by_allowed(e)]
    texts = [r["text"].strip() for r in replies if r.get("author") in ok and _text(r.get("text"))]
    if multi:
        if not by_allowed(CLOSE):
            return Verdict("wait", how="collecting" if (chosen or texts) else "nothing yet")
        parts = [options[i] for i in chosen] + texts
        if not parts:
            return Verdict("unclear", how="✅ with nothing chosen")
        return Verdict("answer", " · ".join(parts), "reactions+text" if texts else "reactions")
    if texts:
        last = texts[-1]
        m = _NUMBERED.match(last)
        if m and int(m.group(1)) <= len(options):
            option = options[int(m.group(1)) - 1]
            note = m.group(2).strip()
            return Verdict("answer", f"{option} — {note}" if note else option, "number reply")
        return Verdict("answer", last, "reply")
    if len(chosen) == 1:
        return Verdict("answer", options[chosen[0]], "reaction")
    if len(chosen) > 1:
        return Verdict("unclear", how="more than one option on a single-select question")
    return Verdict("wait", how="nothing yet")


def kind_label(kind: str) -> str:
    return KIND_LABELS.get(_text(kind), "question")


def message_text(entry: Dict[str, Any], kind: str) -> str:
    """The post: who asks, what kind, the question, the numbered options, how to answer."""
    options = [str(o) for o in entry.get("optionsList") or []]
    multi = bool(entry.get("multi"))
    head = f"❓ **{_text(entry.get('source')) or 'an agent'}** — {kind_label(kind)}"
    lines = []
    for i, o in enumerate(options):
        mark = NUMBERS[i] if i < len(NUMBERS) else f"{i + 1}."
        lines.append(f"{mark} {o}")
    if multi:
        how = "Pick any numbers, add a reply for anything else, then ✅ to send. ❌ leaves it for later."
    else:
        how = ("React with a number, or reply with text (\"2, …\" adds a note to option 2). "
               "❌ leaves it for later.")
    tail = [*lines, "", how, f"`{entry.get('id')}#{entry.get('key')}`"]
    question = _text(entry.get("question"))
    room = MESSAGE_LIMIT - len(head) - sum(len(t) + 1 for t in tail) - 4
    if len(question) > room:
        question = question[:max(room - 1, 0)] + "…"
    return "\n".join([head, question, "", *tail])[:MESSAGE_LIMIT]


# --------------------------------------------------------------------------- #
# post records
# --------------------------------------------------------------------------- #

def posts_dir(base: Optional[Path] = None) -> Path:
    return (base or qr.state_dir()) / "discord" / "posts"


def _private_write(path: Path, data: Dict[str, Any]) -> None:
    path.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    fd = os.open(tmp, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
    with os.fdopen(fd, "w", encoding="utf-8") as fh:
        fh.write(json.dumps(data, ensure_ascii=False, indent=1) + "\n")
    os.replace(tmp, path)


def record_path(cid: str, key: str, base: Optional[Path] = None) -> Path:
    return posts_dir(base) / f"{qr._safe_id(cid)}__{qr._safe_id(key)}.json"


def load_records(base: Optional[Path] = None) -> List[Dict[str, Any]]:
    out = []
    folder = posts_dir(base)
    if not folder.is_dir():
        return out
    for path in sorted(folder.glob("*.json")):
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, ValueError) as exc:
            logger.warning("relay discord: post record %s unreadable (%s)", path.name, type(exc).__name__)
            continue
        if isinstance(data, dict):
            out.append(data)
    return out


def save_record(rec: Dict[str, Any], base: Optional[Path] = None) -> None:
    _private_write(record_path(rec["id"], rec["key"], base), rec)


def prune(base: Optional[Path] = None, now: Optional[float] = None) -> int:
    now = time.time() if now is None else now
    removed = 0
    for rec in load_records(base):
        if rec.get("state") in ("answered", "closed") and now - float(rec.get("ended") or 0) > RETENTION_S:
            try:
                record_path(rec["id"], rec["key"], base).unlink()
                removed += 1
            except OSError:
                pass
    return removed


def waiting_ids(base: Optional[Path] = None) -> Optional[set]:
    """The call ids the relay waits on now; None when that cannot be known (then close nothing)."""
    folder = (base or qr.state_dir()) / "waiting"
    try:
        names = [n for n in os.listdir(folder) if n.endswith(".json")]
    except FileNotFoundError:
        return set()
    except OSError:
        return None
    ids = set()
    for name in names:
        try:
            cid = json.loads((folder / name).read_text(encoding="utf-8")).get("id")
        except (OSError, ValueError, AttributeError):
            return None
        if not isinstance(cid, str) or not cid:
            return None
        ids.add(cid)
    return ids


def answer_path(rec: Dict[str, Any]) -> Path:
    return qr.answer_file(Path(rec["answer_dir"]), rec["id"], rec["key"])


def write_answer(rec: Dict[str, Any], text: str) -> bool:
    """`{"valasz": text}`, mode 600, never over an existing file. False when one already exists."""
    path = answer_path(rec)
    path.parent.mkdir(parents=True, exist_ok=True)
    try:
        fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    except FileExistsError:
        return False
    with os.fdopen(fd, "w", encoding="utf-8") as fh:
        fh.write(json.dumps({"valasz": text}, ensure_ascii=False))
    return True


# --------------------------------------------------------------------------- #
# Discord REST
# --------------------------------------------------------------------------- #

class DiscordError(Exception):
    def __init__(self, status: int, where: str):
        super().__init__(f"Discord answered {status} on {where}")
        self.status = status


Opener = Callable[[urllib.request.Request, float], Tuple[int, bytes, Dict[str, str]]]


def _urlopen(req: urllib.request.Request, timeout: float) -> Tuple[int, bytes, Dict[str, str]]:
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:  # noqa: S310 - fixed API host
            return resp.status, resp.read(), dict(resp.headers)
    except urllib.error.HTTPError as exc:
        return exc.code, exc.read() if exc.fp else b"", dict(exc.headers or {})


class Discord:
    """The handful of REST calls the bridge makes. `opener` is injectable for tests."""

    def __init__(self, token: str, opener: Opener = _urlopen, sleep: Callable[[float], None] = time.sleep):
        self.token, self.opener, self.sleep = token, opener, sleep

    def call(self, method: str, path: str, body: Optional[Dict[str, Any]] = None) -> Any:
        where = f"{method} {re.sub(r'/[0-9]{6,}', '/<id>', path.split('?')[0])}"
        data = json.dumps(body).encode() if body is not None else None
        for attempt in (1, 2):
            req = urllib.request.Request(API + path, data=data, method=method, headers={
                "Authorization": f"Bot {self.token}", "User-Agent": USER_AGENT,
                **({"Content-Type": "application/json"} if data is not None else {})})
            try:
                status, raw, headers = self.opener(req, HTTP_TIMEOUT_S)
            except (OSError, urllib.error.URLError) as exc:
                logger.warning("relay discord: %s failed (%s)", where, type(exc).__name__)
                raise DiscordError(0, where) from exc
            if status == 429 and attempt == 1:
                try:
                    wait = float(json.loads(raw or b"{}").get("retry_after", 1.0))
                except ValueError:
                    wait = 1.0
                self.sleep(min(max(wait, 0.1), 10.0))
                continue
            if status >= 300:
                logger.warning("relay discord: %s → %s", where, status)
                raise DiscordError(status, where)
            return json.loads(raw) if raw else None
        raise DiscordError(429, where)

    def me(self) -> Dict[str, Any]:
        return self.call("GET", "/users/@me")

    def channel(self, channel_id: str) -> Dict[str, Any]:
        return self.call("GET", f"/channels/{channel_id}")

    def send(self, channel_id: str, content: str, reply_to: Optional[str] = None) -> Dict[str, Any]:
        body: Dict[str, Any] = {"content": content[:MESSAGE_LIMIT], "allowed_mentions": {"parse": []}}
        if reply_to:
            body["message_reference"] = {"message_id": reply_to, "fail_if_not_exists": False}
        return self.call("POST", f"/channels/{channel_id}/messages", body)

    def react(self, channel_id: str, message_id: str, emoji: str) -> None:
        self.call("PUT", f"/channels/{channel_id}/messages/{message_id}/reactions/"
                         f"{urllib.parse.quote(emoji)}/@me")

    def message(self, channel_id: str, message_id: str) -> Dict[str, Any]:
        return self.call("GET", f"/channels/{channel_id}/messages/{message_id}")

    def reactors(self, channel_id: str, message_id: str, emoji: str) -> List[str]:
        users = self.call("GET", f"/channels/{channel_id}/messages/{message_id}/reactions/"
                                 f"{urllib.parse.quote(emoji)}?limit=100") or []
        return [str(u.get("id")) for u in users if isinstance(u, dict)]

    def messages_after(self, channel_id: str, after: str, pages: int = REPLY_PAGES) -> List[Dict[str, Any]]:
        """Every message after `after`, oldest first (Discord's page order is not relied on)."""
        out: Dict[int, Dict[str, Any]] = {}
        cursor = after
        for _ in range(pages):
            batch = self.call("GET", f"/channels/{channel_id}/messages?after={cursor}&limit=100") or []
            for m in batch:
                out[int(m["id"])] = m
            if len(batch) < 100:
                break
            cursor = str(max(int(m["id"]) for m in batch))
        return [out[k] for k in sorted(out)]


# --------------------------------------------------------------------------- #
# the commands
# --------------------------------------------------------------------------- #

@dataclass
class World:
    get: Getter = local_config.get
    client: Optional[Discord] = None
    base: Optional[Path] = None
    now: Callable[[], float] = time.time

    def discord(self) -> Discord:
        if self.client is None:
            self.client = Discord(read_token() or "")
        return self.client


def post(payload: str, kind: str, w: World) -> int:
    """The forward command: one message per question. 0 only when every question was posted."""
    gaps = missing(w.get, token=None if w.client is None else "injected")
    if gaps:
        print("set-relay-discord: not configured — missing " + ", ".join(gaps), file=sys.stderr)
        logger.warning("relay discord post: not configured (%s)", ", ".join(gaps))
        return 2
    try:
        envelope = json.loads(payload)
        entries = [e for e in envelope.get("questions") or [] if isinstance(e, dict)]
    except (ValueError, AttributeError):
        entries = []
    if not entries:
        logger.warning("relay discord post: the envelope carries no question")
        return 4
    channel = _text(w.get(KEY_CHANNEL))
    d = w.discord()
    for e in entries:
        cid, key = _text(e.get("id")), _text(e.get("key"))
        options = [str(o) for o in e.get("optionsList") or []]
        multi = bool(e.get("multi"))
        try:
            msg = d.send(channel, message_text(e, kind))
        except DiscordError as exc:
            logger.warning("relay discord post [%s#%s]: not posted (%s)", cid, key, exc.status)
            return 3
        rec = {"id": cid, "key": key, "kind": _text(kind) or "ask", "channel_id": channel,
               "message_id": str(msg["id"]), "options": options, "multi": multi,
               "answer_dir": _text(e.get("valasz_tar")) or str((w.base or qr.state_dir()) / "answers"),
               "posted": w.now(), "state": "open"}
        save_record(rec, w.base)
        for emoji in [*NUMBERS[:len(options)], *((CLOSE,) if multi else ()), DEFER]:
            try:
                d.react(channel, rec["message_id"], emoji)
            except DiscordError as exc:  # a missing reaction still leaves the reply path
                logger.warning("relay discord post [%s#%s]: reaction not added (%s)", cid, key, exc.status)
        logger.info("relay discord post [%s#%s]: posted (%d option(s)%s)", cid, key, len(options),
                    ", multi" if multi else "")
    return 0


def notify(payload: str, w: World) -> int:
    gaps = missing(w.get, token=None if w.client is None else "injected")
    if gaps:
        print("set-relay-discord: not configured — missing " + ", ".join(gaps), file=sys.stderr)
        return 2
    try:
        env = json.loads(payload)
    except ValueError:
        return 4
    if not isinstance(env, dict):
        return 4
    agent = _text(env.get("agent")) or _text(env.get("project")) or "an agent"
    text = f"🔔 **{agent}** — {_text(env.get('message')) or 'needs you at its terminal'}"
    try:
        w.discord().send(_text(w.get(KEY_CHANNEL)), text)
    except DiscordError as exc:
        logger.warning("relay discord notify: not posted (%s)", exc.status)
        return 3
    logger.info("relay discord notify: posted")
    return 0


def _reply(d: Discord, rec: Dict[str, Any], text: str) -> None:
    try:
        d.send(rec["channel_id"], text, reply_to=rec["message_id"])
    except DiscordError as exc:
        logger.warning("relay discord [%s#%s]: reply not posted (%s)", rec["id"], rec["key"], exc.status)


def _end(rec: Dict[str, Any], state: str, w: World, how: str = "") -> None:
    rec.update(state=state, ended=w.now(), how=how)
    save_record(rec, w.base)


def gather(d: Discord, rec: Dict[str, Any], message: Dict[str, Any]) -> Dict[str, List[str]]:
    """Who added which of the bridge's emoji. Only emoji somebody besides the bot added are fetched."""
    wanted = {*NUMBERS[:len(rec["options"])], DEFER, CLOSE}
    out: Dict[str, List[str]] = {}
    for r in message.get("reactions") or []:
        name = _text((r.get("emoji") or {}).get("name"))
        match = next((e for e in wanted if name and (name == e or e.startswith(name) or name.startswith(e))), None)
        if match and int(r.get("count") or 0) - (1 if r.get("me") else 0) > 0:
            out[match] = d.reactors(rec["channel_id"], rec["message_id"], match)
    return out


def poll(w: World) -> Dict[str, int]:
    """One pass over the open posts. Returns counts by outcome (ids only reach the log)."""
    counts: Dict[str, int] = {}
    allowed = allowed_users(w.get)
    if missing(w.get, token=None if w.client is None else "injected"):
        logger.warning("relay discord poll: not configured; nothing read")
        return {"not-configured": 1}
    open_recs = [r for r in load_records(w.base) if r.get("state") == "open"]
    prune(w.base, w.now())
    if not open_recs:
        return counts
    d = w.discord()
    bot_id = _text(w.get(KEY_BOT_ID))
    waiting = waiting_ids(w.base)
    by_channel: Dict[str, List[Dict[str, Any]]] = {}
    for rec in open_recs:
        by_channel.setdefault(rec["channel_id"], []).append(rec)
    replies: Dict[str, List[Dict[str, str]]] = {}
    empty_seen = False
    for channel, recs in by_channel.items():
        try:
            after = str(min(int(r["message_id"]) for r in recs) - 1)
            for m in d.messages_after(channel, after):
                ref = _text((m.get("message_reference") or {}).get("message_id"))
                author = _text((m.get("author") or {}).get("id"))
                if not ref:
                    continue
                if author in allowed and not _text(m.get("content")) and not m.get("attachments"):
                    empty_seen = True
                replies.setdefault(ref, []).append({"author": author, "text": _text(m.get("content"))})
        except DiscordError:
            logger.warning("relay discord poll: replies in a channel unreadable this run")
    if empty_seen:
        logger.warning("relay discord poll: an allowed reply arrived with no text — is the bot's "
                       "Message Content intent on?")

    def bump(name: str) -> None:
        counts[name] = counts.get(name, 0) + 1

    for rec in open_recs:
        tag = f"{rec['id']}#{rec['key']}"
        if answer_path(rec).exists():
            _reply(d, rec, "✔ Answered elsewhere (the fleet, the terminal or the automatic answer); "
                           "nothing was taken from here.")
            _end(rec, "answered", w, "elsewhere")
            logger.info("relay discord [%s]: answered elsewhere", tag)
            bump("answered-elsewhere")
            continue
        if waiting is not None and rec["id"] not in waiting and w.now() - float(rec.get("posted") or 0) > GRACE_S:
            _reply(d, rec, "🔒 Closed — this question no longer waits (it was answered at the terminal, "
                           "released, or timed out). An answer written here would reach nobody.")
            _end(rec, "closed", w, "no longer waits")
            logger.info("relay discord [%s]: closed, no longer waits", tag)
            bump("closed")
            continue
        try:
            message = d.message(rec["channel_id"], rec["message_id"])
            reactions = gather(d, rec, message)
        except DiscordError as exc:
            if exc.status == 404:
                _end(rec, "closed", w, "post deleted")
                logger.info("relay discord [%s]: the post is gone; closed", tag)
                bump("closed")
            else:
                bump("unreadable")
            continue
        verdict = decide(rec["options"], bool(rec.get("multi")), reactions,
                         replies.get(rec["message_id"], []), allowed, bot_id)
        if verdict.state != "answer":
            bump(verdict.state)
            if verdict.state == "unclear" and rec.get("unclear_said") != verdict.how:
                _reply(d, rec, f"⚠ Not taken as an answer: {verdict.how}. Change the reactions or reply with text.")
                rec["unclear_said"] = verdict.how
                save_record(rec, w.base)
            continue
        if not write_answer(rec, verdict.text):
            _end(rec, "answered", w, "elsewhere")
            bump("answered-elsewhere")
            continue
        try:
            d.react(rec["channel_id"], rec["message_id"], RECORDED)
        except DiscordError:
            pass
        _reply(d, rec, f"{RECORDED} Recorded ({verdict.how}): {verdict.text}")
        _end(rec, "answered", w, verdict.how)
        logger.info("relay discord [%s]: answer written (%s)", tag, verdict.how)
        bump("answered")
    return counts


# --------------------------------------------------------------------------- #
# setup, status, test
# --------------------------------------------------------------------------- #

def bridge_command(sub: str) -> str:
    here = Path(__file__).resolve().parents[3] / "bin" / "set-relay-discord"
    exe = shutil.which("set-relay-discord") or str(here)
    return f"{exe} {sub}"


def wiring_key(get: Getter = local_config.get) -> str:
    """D7: behind the auto-answer outbound when that is the relay's command, else the relay's own."""
    cmd = _text(get(qr.KEY_COMMAND))
    first = cmd.split()[0] if cmd else ""
    return KEY_AA_FORWARD if Path(first).name == "set-auto-answer" else qr.KEY_COMMAND


def unit_texts(command: str) -> Dict[str, str]:
    service = ("[Unit]\nDescription=Take question-relay answers from Discord\n\n"
               "[Service]\nType=oneshot\n"
               f"ExecStart={command}\n")
    timer = ("[Unit]\nDescription=Read question-relay answers from Discord every minute\n\n"
             "[Timer]\nOnBootSec=60\nOnUnitActiveSec=60\nAccuracySec=5\n\n"
             "[Install]\nWantedBy=timers.target\n")
    return {f"{UNIT_NAME}.service": service, f"{UNIT_NAME}.timer": timer}


def unit_dir() -> Path:
    return Path(os.environ.get("XDG_CONFIG_HOME") or Path.home() / ".config") / "systemd" / "user"


def install_timer(systemctl: Callable[..., Any] = subprocess.run, folder: Optional[Path] = None) -> Path:
    folder = folder or unit_dir()
    folder.mkdir(parents=True, exist_ok=True)
    for name, text in unit_texts(bridge_command("poll")).items():
        (folder / name).write_text(text, encoding="utf-8")
    systemctl(["systemctl", "--user", "daemon-reload"], check=True)
    systemctl(["systemctl", "--user", "enable", "--now", f"{UNIT_NAME}.timer"], check=True)
    logger.info("relay discord: timer installed in %s", folder)
    return folder


def remove_timer(systemctl: Callable[..., Any] = subprocess.run, folder: Optional[Path] = None) -> None:
    folder = folder or unit_dir()
    systemctl(["systemctl", "--user", "disable", "--now", f"{UNIT_NAME}.timer"], check=False)
    for name in unit_texts("x"):
        try:
            (folder / name).unlink()
        except FileNotFoundError:
            pass
    systemctl(["systemctl", "--user", "daemon-reload"], check=False)


def setup(args: argparse.Namespace, w: World, *, set_value: Callable[[str, Any], Any] = local_config.set_value,
          systemctl: Callable[..., Any] = subprocess.run, out: Callable[[str], None] = print,
          token_file: Optional[Path] = None, units: Optional[Path] = None) -> int:
    token_file = token_file or token_path()
    if args.remove:
        prev = _text(w.get(KEY_PREVIOUS))
        try:
            p = json.loads(prev) if prev else {}
        except ValueError:
            p = {}
        for key, value in (p.items() if isinstance(p, dict) else []):
            set_value(key, value)
            out(f"restored {key}")
        remove_timer(systemctl, units)
        out(f"timer {UNIT_NAME}.timer removed; the token file and the channel settings were kept")
        return 0
    if args.token_stdin:
        token = sys.stdin.readline().strip()
        if not token:
            out("✗ no token on stdin")
            return 1
        token_file.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
        fd = os.open(token_file, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
        with os.fdopen(fd, "w", encoding="utf-8") as fh:
            fh.write(token + "\n")
        os.chmod(token_file, 0o600)
        out(f"✓ token stored in {token_file} (mode 600)")
    if args.channel:
        set_value(KEY_CHANNEL, args.channel)
        out(f"✓ {KEY_CHANNEL} set")
    if args.allow:
        ids = [i for i in re.split(r"[\s,]+", " ".join(args.allow)) if i.isdigit()]
        set_value(KEY_ALLOWED, json.dumps(ids))
        out(f"✓ {KEY_ALLOWED}: {len(ids)} user(s)")
    gaps = missing(w.get, token=read_token(token_file))
    if gaps:
        out("✗ still missing: " + ", ".join(gaps))
        return 1
    d = w.client or Discord(read_token(token_file) or "")
    try:
        me = d.me()
        set_value(KEY_BOT_ID, str(me.get("id")))
        out(f"✓ token works — bot {me.get('username')} ({me.get('id')})")
        d.channel(_text(w.get(KEY_CHANNEL)))
        out("✓ the bot can see the channel")
    except DiscordError as exc:
        out(f"✗ Discord refused: {exc} — check the token, and that the bot is in the channel's server")
        return 1
    key = wiring_key(w.get)
    current = _text(w.get(key))
    want = bridge_command("post")
    previous: Dict[str, Any] = {}
    if current and current != want:
        if not args.replace:
            out(f"✗ {key} already points to another command:\n    {current}\n"
                "  Nothing was rewired. Run setup again with --replace to use this bridge instead.")
            return 2
        previous[key] = current
    set_value(key, want)
    out(f"✓ {key} → {want}")
    if key == qr.KEY_COMMAND:
        set_value(qr.KEY_TARGET, "command")
    notify_cmd = _text(w.get(qr.KEY_NOTIFY_COMMAND))
    want_notify = bridge_command("notify")
    if not notify_cmd or (args.replace and notify_cmd != want_notify):
        if notify_cmd:
            previous[qr.KEY_NOTIFY_COMMAND] = notify_cmd
        set_value(qr.KEY_NOTIFY_COMMAND, want_notify)
        out(f"✓ {qr.KEY_NOTIFY_COMMAND} → {want_notify}")
    elif notify_cmd != want_notify:
        out(f"· {qr.KEY_NOTIFY_COMMAND} kept (another command; --replace to change it)")
    if previous:
        set_value(KEY_PREVIOUS, json.dumps(previous, ensure_ascii=False))
    if not _text(w.get(qr.KEY_AUDIENCE)):
        set_value(qr.KEY_AUDIENCE, "DEV")
        out(f"✓ {qr.KEY_AUDIENCE} = DEV (the relay needs one)")
    folder = install_timer(systemctl, units)
    out(f"✓ timer {UNIT_NAME}.timer installed in {folder}, every minute")
    state = qr.readiness(w.get)
    out(f"· question relay: {'ON' if state['enabled'] else 'off'}"
        + ("" if state["ready"] else f", missing {', '.join(state['missing'])}")
        + " — switch it on in the fleet header or with `set-config set question_relay.enabled true`.")
    out("· The bot needs the Message Content intent (Developer Portal → Bot) to read replies; "
        "`set-relay-discord test` checks it.")
    return 0


def status(w: World, out: Callable[[str], None] = print, systemctl: Callable[..., Any] = subprocess.run) -> int:
    gaps = missing(w.get)
    out(f"token file: {token_path()} ({'present' if read_token() else 'missing'})")
    out(f"channel: {_text(w.get(KEY_CHANNEL)) or '—'} · allowed users: {len(allowed_users(w.get))}")
    out(f"relay command ({wiring_key(w.get)}): {_text(w.get(wiring_key(w.get))) or '—'}")
    out(f"notify command: {_text(w.get(qr.KEY_NOTIFY_COMMAND)) or '—'}")
    try:
        res = systemctl(["systemctl", "--user", "is-active", f"{UNIT_NAME}.timer"],
                        capture_output=True, text=True, check=False)
        out(f"timer: {(res.stdout or '').strip() or 'unknown'}")
    except OSError:
        out("timer: unknown")
    recs = load_records(w.base)
    out("posts: " + ", ".join(f"{s} {sum(1 for r in recs if r.get('state') == s)}"
                              for s in ("open", "answered", "closed")))
    if gaps:
        out("missing: " + ", ".join(gaps))
        return 1
    try:
        me = w.discord().me()
        out(f"token check: ok — bot {me.get('username')}")
    except DiscordError as exc:
        out(f"token check: FAILED ({exc.status})")
        return 1
    return 0


def test(w: World, out: Callable[[str], None] = print) -> int:
    gaps = missing(w.get, token=None if w.client is None else "injected")
    if gaps:
        out("missing: " + ", ".join(gaps))
        return 1
    try:
        msg = w.discord().send(_text(w.get(KEY_CHANNEL)),
                               "🧪 set-relay-discord test — reply to this message with any word within "
                               "two minutes and run `set-relay-discord test --check` to see whether the "
                               "bot can read replies (the Message Content intent).")
    except DiscordError as exc:
        out(f"✗ the probe was not posted ({exc.status})")
        return 1
    _private_write((w.base or qr.state_dir()) / "discord" / "probe.json",
                   {"channel_id": _text(w.get(KEY_CHANNEL)), "message_id": str(msg["id"])})
    out("✓ probe posted — reply to it, then run `set-relay-discord test --check`")
    return 0


def test_check(w: World, out: Callable[[str], None] = print) -> int:
    try:
        probe = json.loads(((w.base or qr.state_dir()) / "discord" / "probe.json").read_text(encoding="utf-8"))
    except (OSError, ValueError):
        out("no probe yet — run `set-relay-discord test` first")
        return 1
    allowed = allowed_users(w.get)
    try:
        msgs = w.discord().messages_after(probe["channel_id"], str(int(probe["message_id"]) - 1), pages=1)
    except DiscordError as exc:
        out(f"✗ messages unreadable ({exc.status})")
        return 1
    replies = [m for m in msgs if _text((m.get("message_reference") or {}).get("message_id")) == probe["message_id"]
               and _text((m.get("author") or {}).get("id")) in allowed]
    if not replies:
        out("no reply from an allowed user yet")
        return 1
    if all(not _text(m.get("content")) for m in replies):
        out("✗ the reply arrived with NO text: turn on the bot's Message Content intent "
            "(Developer Portal → your app → Bot → Privileged Gateway Intents)")
        return 1
    out("✓ replies are readable — reactions and text answers will both work")
    return 0


# --------------------------------------------------------------------------- #
# CLI
# --------------------------------------------------------------------------- #

def _log_to_file() -> None:
    path = qr.state_dir() / "relay-discord.log"
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        handler = logging.FileHandler(path, encoding="utf-8")
    except OSError:
        return
    handler.setFormatter(logging.Formatter("%(asctime)s %(levelname)s %(name)s: %(message)s"))
    root = logging.getLogger("set_orch")
    root.addHandler(handler)
    root.setLevel(logging.INFO)


def main(argv: Optional[List[str]] = None, w: Optional[World] = None) -> int:
    parser = argparse.ArgumentParser(prog="set-relay-discord", description=__doc__.split("\n\n")[0])
    sub = parser.add_subparsers(dest="cmd", required=True)
    sub.add_parser("post", help="the relay's forward command: the envelope on stdin")
    sub.add_parser("notify", help="the relay's notify command: the notification on stdin")
    sub.add_parser("poll", help="read answers from Discord once (the timer runs this)")
    s = sub.add_parser("setup", help="wire this machine")
    s.add_argument("--channel", help="the channel id")
    s.add_argument("--allow", nargs="*", default=[], help="Discord user ids whose answers count")
    s.add_argument("--token-stdin", action="store_true", help="read the bot token from stdin")
    s.add_argument("--replace", action="store_true", help="replace another configured bridge")
    s.add_argument("--remove", action="store_true", help="stop the timer and restore the previous commands")
    sub.add_parser("status", help="what is configured and whether it works")
    t = sub.add_parser("test", help="post a probe message")
    t.add_argument("--check", action="store_true", help="check the reply to the probe")
    args = parser.parse_args(argv)
    _log_to_file()
    w = w or World()
    if args.cmd == "post":
        return post(sys.stdin.read(), os.environ.get(qr.ENV_KIND, "ask"), w)
    if args.cmd == "notify":
        return notify(sys.stdin.read(), w)
    if args.cmd == "poll":
        counts = poll(w)
        if counts:
            logger.info("relay discord poll: %s", ", ".join(f"{k} {v}" for k, v in sorted(counts.items())))
        return 0
    if args.cmd == "setup":
        return setup(args, w)
    if args.cmd == "status":
        return status(w)
    if args.cmd == "test":
        return test_check(w) if args.check else test(w)
    return 1
