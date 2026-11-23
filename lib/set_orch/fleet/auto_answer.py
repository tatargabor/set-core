"""Answer a relayed blocking point on the operator's behalf — the decision core.

`set-auto-answer` sits in front of the operator's real outbound (fleet-auto-answer, D1):
the relay hands it the envelope, and it decides — by a FORK of the asking session (D8) —
what the operator would answer, with references that are then checked verbatim. This
module holds the decision: configuration, the parser, the exclusions, the allow rule,
the knowledge-base step, the fork and its fallback, and the reference check. The worker
that forwards, waits out the window and writes is `auto_answer_worker`.

Three rules shape it, and each one has a fail direction:

- **An outward or irreversible step is never answered automatically** (D6). Two checks,
  either one excludes: a deterministic pattern over the question, the options and the
  chosen answer, and the model's own flag. A false positive forwards a question to a
  person; a false negative approves a publish in the operator's name.
- **The tier is derived, never taken from the model** (D8). A quote counts only if it
  occurs verbatim in an OPERATOR turn before the question; an excerpt only if it occurs
  verbatim in the file. A self-assigned `decided` was wrong 8 times in 21 in the replay.
- **No text in the logs** (D9). Log lines carry counts, tiers, outcomes and reasons. The
  question and answer text goes only into the machine-local decision log the worker
  writes, which is the operator's own audit trail.
"""

from __future__ import annotations

import json
import logging
import os
import re
import shutil
import signal
import subprocess
import tempfile
import time
import unicodedata
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any, Callable, Dict, Iterable, List, Optional, Sequence, Tuple

from .. import local_config

logger = logging.getLogger(__name__)

Getter = Callable[..., Any]

# --------------------------------------------------------------------------- #
# configuration (task 2.1)
# --------------------------------------------------------------------------- #

KEY_ENABLED = "auto_answer.enabled"
KEY_FORWARD = "auto_answer.forward_command"
KEY_WINDOW = "auto_answer.window_s"
KEY_LIKELY_MIN = "auto_answer.likely_min"
KEY_MODEL = "auto_answer.model"
KEY_NEVER = "auto_answer.never_patterns"
KEY_EXTRA = "auto_answer.extra_paths"
KEY_LOG_DAYS = "auto_answer.log_days"
KEY_DECIDE_TIMEOUT = "auto_answer.decide_timeout_s"

DEFAULT_WINDOW_S = 60.0
DEFAULT_LIKELY_MIN = 0.8
DEFAULT_FALLBACK_MODEL = "sonnet"
DEFAULT_LOG_DAYS = 90
DEFAULT_DECIDE_TIMEOUT_S = 120.0
KB_LIMIT = 6
KB_TIMEOUT_S = 30.0
KB_QUERY_CHARS = 400

#: Set on the fork's environment: the fork must never relay its own questions, and a
#: hook that does run (hooks are disabled too) can tell it is inside a decision.
GUARD_ENV = "SET_AUTO_ANSWER_FORK"
#: The wait detector's guard, set as well, so a Stop in the fork never classifies.
WAIT_DETECT_GUARD_ENV = "SET_WAIT_DETECT_CLASSIFIER"

KIND_ASK = "ask"
KIND_PERMISSION = "permission"
KIND_CONTINUATION = "continuation"

TIER_DECIDED, TIER_FOUND, TIER_LIKELY = "decided", "found", "likely"
TIERS = (TIER_DECIDED, TIER_FOUND, TIER_LIKELY)


def _text(value: Any) -> str:
    return str(value).strip() if value is not None else ""


def _truthy(value: Any) -> bool:
    return _text(value).lower() in ("1", "true", "yes", "on")


def _number(get: Getter, key: str, default: float, low: float, high: float) -> float:
    raw = get(key)
    if raw is None or _text(raw) == "":
        return default
    try:
        value = float(raw)
    except (TypeError, ValueError):
        logger.warning("auto answer: %s=%r is not a number; using %s", key, raw, default)
        return default
    if not (low <= value <= high):
        logger.warning("auto answer: %s=%s outside [%s, %s]; using %s", key, value, low, high, default)
        return default
    return value


def enabled(get: Getter = local_config.get) -> bool:
    return _truthy(get(KEY_ENABLED))


def forward_command(get: Getter = local_config.get) -> str:
    return _text(get(KEY_FORWARD))


def window_s(get: Getter = local_config.get) -> float:
    return _number(get, KEY_WINDOW, DEFAULT_WINDOW_S, 0.0, 3000.0)


def likely_min(get: Getter = local_config.get) -> float:
    return _number(get, KEY_LIKELY_MIN, DEFAULT_LIKELY_MIN, 0.0, 1.0)


def fallback_model(get: Getter = local_config.get) -> str:
    return _text(get(KEY_MODEL)) or DEFAULT_FALLBACK_MODEL


def log_days(get: Getter = local_config.get) -> float:
    return _number(get, KEY_LOG_DAYS, DEFAULT_LOG_DAYS, 1.0, 3650.0)


def decide_timeout_s(get: Getter = local_config.get) -> float:
    return _number(get, KEY_DECIDE_TIMEOUT, DEFAULT_DECIDE_TIMEOUT_S, 5.0, 1800.0)


def _list(get: Getter, key: str) -> List[str]:
    """A JSON list, or one entry per line. Either shape, because `set-config set` takes a string."""
    raw = get(key)
    if raw is None:
        return []
    if isinstance(raw, (list, tuple)):
        return [_text(x) for x in raw if _text(x)]
    text = _text(raw)
    if text.startswith("["):
        try:
            data = json.loads(text)
            if isinstance(data, list):
                return [_text(x) for x in data if _text(x)]
        except ValueError:
            logger.warning("auto answer: %s is not a valid JSON list; read one entry per line", key)
    return [line.strip() for line in text.splitlines() if line.strip()]


def never_patterns(get: Getter = local_config.get) -> List[str]:
    return _list(get, KEY_NEVER)


def extra_paths(get: Getter = local_config.get) -> List[str]:
    return _list(get, KEY_EXTRA)


# --------------------------------------------------------------------------- #
# the decision and its parser (task 2.2)
# --------------------------------------------------------------------------- #

@dataclass
class Reference:
    kind: str                     # "operator" | "file"
    quote: str = ""               # the operator's words, or the file excerpt
    path: str = ""                # file references only
    decision: bool = False        # a file excerpt that records a decision
    checked: Optional[bool] = None
    reason: str = ""

    def as_record(self) -> Dict[str, Any]:
        out: Dict[str, Any] = {"kind": self.kind, "quote": self.quote, "checked": self.checked}
        if self.path:
            out["path"] = self.path
        if self.decision:
            out["decision"] = True
        if self.reason:
            out["reason"] = self.reason
        return out


@dataclass
class Answer:
    key: str
    choice: str
    claimed_tier: str
    confidence: float
    outward: bool
    references: List[Reference] = field(default_factory=list)
    tier: str = ""                # derived by check_references
    note: str = ""                # the model's one-line reason, if it gave one


@dataclass
class Question:
    key: str
    text: str
    options: List[str]
    multi: bool = False


def questions_of(envelope: Dict[str, Any]) -> List[Question]:
    out = []
    for q in envelope.get("questions") or []:
        if isinstance(q, dict) and _text(q.get("key")):
            out.append(Question(key=_text(q.get("key")), text=str(q.get("question") or ""),
                                options=[str(o) for o in q.get("optionsList") or [] if _text(o)],
                                multi=bool(q.get("multi"))))
    return out


_FENCE = re.compile(r"```(?:json)?\s*(\{.*?\})\s*```", re.S)


def _json_object(raw: str) -> Optional[Dict[str, Any]]:
    """The one JSON object in the model's reply: whole, fenced, or between the outer braces."""
    text = (raw or "").strip()
    candidates = [text]
    candidates += [m.group(1) for m in _FENCE.finditer(text)]
    if "{" in text and "}" in text:
        candidates.append(text[text.index("{"): text.rindex("}") + 1])
    for c in candidates:
        try:
            data = json.loads(c)
        except ValueError:
            continue
        if isinstance(data, dict):
            return data
    return None


def _confidence(value: Any) -> Optional[float]:
    if isinstance(value, bool):
        return None
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    return number if 0.0 <= number <= 1.0 else None


def _choice_text(value: Any, q: Question) -> Optional[str]:
    """The choice as the answer text the relay writes, or None when it is not a valid one."""
    if q.multi:
        items = value if isinstance(value, list) else [s.strip() for s in _text(value).split(",")]
        items = [_text(i) for i in items if _text(i)]
        if not items or (q.options and any(i not in q.options for i in items)):
            return None
        return ", ".join(items)
    if isinstance(value, (list, dict)):
        return None
    choice = _text(value)
    return choice or None


def parse_decision(raw: str, questions: Sequence[Question], kind: str) -> Tuple[Dict[str, Answer], Dict[str, str]]:
    """The model's reply → one Answer per question it validly answered, and a reason per refusal.

    Refused, per question: no JSON object, no entry for the key, an abstention (null
    choice), a missing or unknown tier, a `decided`/`found` with no reference, a `likely`
    without a confidence in [0, 1], and — for a closed option list — a choice that is not
    one of the options. A continuation's choice may be free text: its options are
    suggestions, and the operator's real answer is often an instruction of their own.
    """
    answers: Dict[str, Answer] = {}
    refused: Dict[str, str] = {}
    data = _json_object(raw)
    if data is None:
        return {}, {q.key: "no JSON object in the reply" for q in questions}
    entries = data.get("answers")
    if not isinstance(entries, list):
        entries = [data] if len(questions) == 1 else []
    by_key: Dict[str, Dict[str, Any]] = {}
    for e in entries:
        if isinstance(e, dict):
            key = _text(e.get("key")) or (questions[0].key if len(questions) == 1 else "")
            if key and key not in by_key:
                by_key[key] = e
    for q in questions:
        e = by_key.get(q.key)
        if e is None:
            refused[q.key] = "no entry for the question"
            continue
        if e.get("choice") is None or (isinstance(e.get("choice"), str) and not e["choice"].strip()):
            refused[q.key] = "abstained"
            continue
        tier = _text(e.get("tier")).lower()
        if tier not in TIERS:
            refused[q.key] = "missing or unknown tier"
            continue
        refs = []
        for r in e.get("references") or []:
            if not isinstance(r, dict):
                continue
            rkind = _text(r.get("kind")).lower()
            quote = str(r.get("quote") or r.get("excerpt") or "")
            if rkind == "operator" and quote.strip():
                refs.append(Reference(kind="operator", quote=quote))
            elif rkind in ("file", "decision") and quote.strip() and _text(r.get("path")):
                refs.append(Reference(kind="file", quote=quote, path=_text(r.get("path")),
                                      decision=rkind == "decision" or bool(r.get("decision"))))
        if tier in (TIER_DECIDED, TIER_FOUND) and not refs:
            refused[q.key] = f"tier {tier} without a reference"
            continue
        conf = _confidence(e.get("confidence"))
        if tier == TIER_LIKELY and conf is None:
            refused[q.key] = "likely without a confidence in [0, 1]"
            continue
        choice = _choice_text(e.get("choice"), q)
        if choice is None:
            refused[q.key] = "not a valid choice"
            continue
        closed = kind != KIND_CONTINUATION and bool(q.options)
        if closed and not q.multi and choice not in q.options:
            refused[q.key] = "choice outside the options"
            continue
        answers[q.key] = Answer(key=q.key, choice=choice, claimed_tier=tier,
                                confidence=conf if conf is not None else 0.0,
                                outward=_truthy(e.get("outward")),
                                references=refs, note=_text(e.get("reason"))[:300])
    return answers, refused


# --------------------------------------------------------------------------- #
# the exclusions (task 2.3)
# --------------------------------------------------------------------------- #

#: Families of outward or irreversible steps. Matched on ASCII-folded, lower-cased text,
#: anchored at a word start and a word end, so "products" does not fire `prod` and
#: "payload" does not fire `pay`. Hungarian forms are written folded (élesít → elesit).
#: The list is the floor; `auto_answer.never_patterns` extends it per machine.
EXCLUSION_FAMILIES: Dict[str, Tuple[str, ...]] = {
    "publish": (r"push\w*", r"publish\w*", r"publik\w*", r"kozze\w*", r"release\w*",
                r"upload\w*", r"feltolt\w*", r"tag(?:s|ged|ging)? (?:and|&) push\w*"),
    "deploy": (r"deploy\w*", r"elesit\w*", r"rollout\w*", r"roll out", r"kitelepit\w*"),
    "production": (r"prod", r"production\w*", r"produkci\w*", r"eles\w*", r"live (?:system|site|server)"),
    "send": (r"send\w*", r"sent", r"e-?mail\w*", r"kuld\w*", r"uzen\w*",
             r"post(?:s|ed|ing)? (?:to|in|on)", r"notify\w*", r"ertesit\w*"),
    "delete": (r"delete\w*", r"torol\w*", r"torl\w*", r"purge\w*", r"wipe\w*", r"destroy\w*",
               r"drop (?:the )?(?:table|database|schema|db)\w*", r"rm -rf", r"reset --hard",
               r"force[- ]?push\w*", r"--force"),
    "pay": (r"pay", r"pays", r"paying", r"paid", r"payment\w*", r"payout\w*", r"purchase\w*",
            r"buy", r"buying", r"fizet\w*", r"fizess\w*", r"kifizet\w*", r"atutal\w*", r"vasarol\w*", r"vasarl\w*", r"szamlaz\w*",
            r"megrendel\w*"),
    "credential": (r"credential\w*", r"password\w*", r"passwd", r"jelszo\w*", r"secret\w*",
                   r"(?:api|access|auth|bearer)[ _-]?(?:key|token)s?", r"private key\w*",
                   r"ssh[ -]?key\w*"),
}


def fold(text: str) -> str:
    """Lower case, accents removed: `Élesítés` and `elesites` are the same word here."""
    decomposed = unicodedata.normalize("NFKD", text or "")
    return "".join(c for c in decomposed if not unicodedata.combining(c)).lower()


def _compile(fragment: str) -> re.Pattern:
    return re.compile(r"(?<![\w-])(?:" + fragment + r")(?![\w])")


_COMPILED = {fam: [_compile(f) for f in frags] for fam, frags in EXCLUSION_FAMILIES.items()}


def _extra_compiled(patterns: Iterable[str]) -> List[re.Pattern]:
    out = []
    for p in patterns:
        try:
            out.append(_compile(fold(p)))
        except re.error:
            # A broken pattern still has to exclude what it names: read it literally.
            logger.warning("auto answer: never_pattern %r is not a valid regex; matched literally", p)
            out.append(_compile(re.escape(fold(p))))
    return out


def outward_hits(texts: Iterable[str], never: Iterable[str] = ()) -> List[str]:
    """The families (and `never_patterns`) that fire anywhere in `texts`, in a stable order."""
    folded = [fold(t) for t in texts if t]
    hits = []
    for fam, pats in _COMPILED.items():
        if any(p.search(t) for p in pats for t in folded):
            hits.append(fam)
    if any(p.search(t) for p in _extra_compiled(never) for t in folded):
        hits.append("never_patterns")
    return hits


def exclusion(kind: str, question: Question, choice: str, model_outward: bool,
              never: Iterable[str] = ()) -> Optional[str]:
    """Why this answer may not be written automatically, or None. Any one reason excludes."""
    if kind == KIND_PERMISSION:
        return "permission prompt"
    hits = outward_hits([question.text, *question.options, choice], never)
    if hits:
        return "outward step: " + ", ".join(hits)
    if model_outward:
        return "outward step: flagged by the model"
    return None


# --------------------------------------------------------------------------- #
# the allow rule (task 2.4)
# --------------------------------------------------------------------------- #

OUTCOME_ALLOWED = "allowed"
OUTCOME_EXCLUDED = "excluded"
OUTCOME_BELOW_BAR = "below-bar"


def allow(tier: str, confidence: float, excluded: Optional[str], bar: float) -> str:
    """`allowed`, `excluded` or `below-bar`. An exclusion outranks every tier."""
    if excluded:
        return OUTCOME_EXCLUDED
    if tier in (TIER_DECIDED, TIER_FOUND):
        return OUTCOME_ALLOWED
    if tier == TIER_LIKELY and confidence >= bar:
        return OUTCOME_ALLOWED
    return OUTCOME_BELOW_BAR


# --------------------------------------------------------------------------- #
# the knowledge-base step (task 2.5a)
# --------------------------------------------------------------------------- #

Runner = Callable[..., Any]


def kb_candidates(questions: Sequence[Question], cwd: str, *, run: Runner = subprocess.run,
                  limit: int = KB_LIMIT) -> Tuple[List[Dict[str, str]], str]:
    """Ranked sections from `set-kb search --json`, and a note for the log.

    The decider runs the search, not the model, so the model keeps read-only tools and
    needs no shell (D8a). Any failure — no binary, a non-zero exit, a reply that is not
    the JSON contract, a timeout — continues without the kb and says why.
    """
    exe = shutil.which("set-kb")
    if not exe:
        return [], "kb: not used (set-kb not on PATH)"
    query = " ".join(" ".join([q.text, *q.options]) for q in questions)
    query = re.sub(r"\s+", " ", query).strip()[:KB_QUERY_CHARS]
    if not query:
        return [], "kb: not used (empty question)"
    try:
        res = run([exe, "search", "--json", "--limit", str(limit), query], cwd=cwd or None,
                  stdout=subprocess.PIPE, stderr=subprocess.DEVNULL, text=True, timeout=KB_TIMEOUT_S)
    except subprocess.TimeoutExpired:
        return [], f"kb: not used (timed out after {KB_TIMEOUT_S:.0f} s)"
    except OSError as exc:
        return [], f"kb: not used ({type(exc).__name__})"
    if getattr(res, "returncode", 1) != 0:
        return [], f"kb: not used (exit {res.returncode})"
    try:
        data = json.loads(res.stdout or "")
        hits = data.get("hits") if isinstance(data, dict) else None
    except ValueError:
        hits = None
    if not isinstance(hits, list):
        return [], "kb: not used (no hits list in the reply)"
    out = []
    for h in hits:
        if isinstance(h, dict) and _text(h.get("path")):
            out.append({"path": _text(h.get("path")),
                        "heading": _text(h.get("headingPath") or h.get("heading")),
                        "excerpt": re.sub(r"\s+", " ", str(h.get("snippet") or "")).strip()[:400]})
    return out, f"kb: {len(out)} hit(s)"


# --------------------------------------------------------------------------- #
# where the session is, and what it runs on (task 2.5)
# --------------------------------------------------------------------------- #

SESSION_RECORD_DIR = Path.home() / ".claude" / "sessions"
PROJECTS_DIR = Path.home() / ".claude" / "projects"


def transcript_of(session_id: str, projects: Path = PROJECTS_DIR) -> Optional[Path]:
    if not re.fullmatch(r"[A-Za-z0-9-]{8,}", session_id or ""):
        return None
    for path in projects.glob(f"*/{session_id}.jsonl"):
        if path.is_file():
            return path
    return None


def transcript_model(path: Path, tail: int = 1 << 20) -> Optional[str]:
    """The model of the session's newest assistant entry (`message.model`, measured S4)."""
    try:
        size = path.stat().st_size
        with path.open("rb") as handle:
            handle.seek(max(0, size - tail))
            lines = handle.read().splitlines()
    except OSError:
        return None
    for line in reversed(lines):
        if b'"model"' not in line:
            continue
        try:
            entry = json.loads(line)
        except ValueError:
            continue
        message = entry.get("message") if isinstance(entry, dict) else None
        model = message.get("model") if isinstance(message, dict) else None
        if entry.get("type") == "assistant" and isinstance(model, str) and model and not model.startswith("<"):
            return model
    return None


def session_pid(session_id: str, records: Path = SESSION_RECORD_DIR) -> Optional[int]:
    """The live process of a session, from the runtime's own per-pid records."""
    try:
        files = list(records.glob("*.json"))
    except OSError:
        return None
    for path in files:
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            continue
        if isinstance(data, dict) and data.get("sessionId") == session_id:
            try:
                return int(data.get("pid"))
            except (TypeError, ValueError):
                return None
    return None


def unit_of(pid: int, proc: Path = Path("/proc")) -> Optional[str]:
    """The systemd unit a process runs in — what the provider record is keyed on."""
    try:
        text = (proc / str(pid) / "cgroup").read_text(encoding="utf-8")
    except OSError:
        return None
    for line in text.splitlines():
        last = line.rsplit("/", 1)[-1].strip()
        if last.endswith((".scope", ".service")):
            return last
    return None


@dataclass
class Launch:
    argv: List[str]               # the command up to (not including) the fork's own flags
    env: Dict[str, str]
    unset: Tuple[str, ...]
    provider: str
    model: str
    source: str                   # "record" | "transcript"

    def describe(self) -> str:
        return f"{self.provider}/{self.model} (from the {self.source})"


def _plan_launch(provider: str, model: Optional[str], source: str, resolve: Callable[..., Any]) -> Optional[Launch]:
    from ..providers import UnknownModel
    try:
        plan = resolve(provider=provider, model=model)
    except UnknownModel:
        # The session's measured model is not in the catalogue: keep the provider, and
        # pass the model as the caller's value, which `launch_args` lets win.
        plan = resolve(provider=provider)
    base = ["claude"] + (["--model", model] if model else [])
    return Launch(argv=base + list(plan.launch_args(base)), env=dict(plan.env), unset=tuple(plan.unset),
                  provider=plan.provider, model=model or plan.model, source=source)


def session_launch(session_id: str, transcript: Optional[Path], *,
                   pid_of: Callable[[str], Optional[int]] = session_pid,
                   unit: Callable[[int], Optional[str]] = unit_of,
                   record_get: Optional[Callable[[str], Optional[Dict[str, Any]]]] = None,
                   resolve: Optional[Callable[..., Any]] = None,
                   catalogue: Optional[Callable[[], Dict[str, Any]]] = None) -> Optional[Launch]:
    """How to start a fork on the SAME model and provider as the session (D8), or None.

    The fleet's provider record wins (keyed on the session's unit); else the transcript's
    newest model: a `claude-*` model runs on the CLI's own login, a model in another
    provider's catalogue (a GLM session) runs on that provider's plan. A session whose
    model cannot be placed is not forked on a guess — the caller falls back.
    """
    from .. import providers
    from . import provider_record
    record_get = record_get or provider_record.get
    resolve = resolve or providers.resolve
    catalogue = catalogue or providers.catalogue
    try:
        pid = pid_of(session_id)
        u = unit(pid) if pid else None
        recorded = record_get(u) if u else None
        if recorded and recorded.get("provider"):
            return _plan_launch(str(recorded["provider"]), recorded.get("model"), "record", resolve)
        model = transcript_model(transcript) if transcript else None
        if not model:
            return None
        if model.startswith("claude-"):
            return Launch(argv=["claude", "--model", model], env={}, unset=(), provider="anthropic",
                          model=model, source="transcript")
        for p in catalogue().get("providers") or []:
            if model in (p.get("models") or []) and p.get("name") != "anthropic":
                return _plan_launch(str(p["name"]), model, "transcript", resolve)
        logger.warning("auto answer: the session's model is in no provider's catalogue; not forked")
        return None
    except Exception as exc:  # a provider error must not stop the decision, only the fork
        logger.warning("auto answer: the session's provider could not be resolved (%s)", type(exc).__name__)
        return None


# --------------------------------------------------------------------------- #
# the prompt
# --------------------------------------------------------------------------- #

def decision_locations(cwd: str, extra: Sequence[str] = (), home: Path = Path.home()) -> List[str]:
    """Where decisions live, as paths that exist — the fork is pointed at them, not given them."""
    root = Path(cwd) if cwd else None
    found: List[str] = []

    def add(p: Path) -> None:
        if p.exists() and str(p) not in found:
            found.append(str(p))

    add(home / ".claude" / "CLAUDE.md")
    if root:
        for rel in ("CLAUDE.md", ".claude/CLAUDE.md", ".claude/rules", "openspec/bugs/README.md"):
            add(root / rel)
        handoffs = sorted((root / ".set" / "handoff").glob("*.md"), key=lambda p: p.stat().st_mtime,
                          reverse=True) if (root / ".set" / "handoff").is_dir() else []
        if handoffs:
            add(handoffs[0])
        changes = root / "openspec" / "changes"
        if changes.is_dir():
            for c in sorted(changes.iterdir()):
                if c.is_dir() and c.name != "archive":
                    add(c)
        add(home / ".claude" / "projects" / re.sub(r"[^A-Za-z0-9-]", "-", str(root)) / "memory")
    for e in extra:
        add(Path(os.path.expanduser(e)) if os.path.isabs(os.path.expanduser(e)) or not root else root / e)
    return found


PROMPT_HEAD = """You are deciding, on the OPERATOR's behalf, how they would answer a question an agent \
just asked. You are a fork of the agent's own session: the conversation above is real, and the \
operator's own messages in it are the strongest evidence you have.

Predict the OPERATOR's answer — not the agent's recommendation, and not what seems best to you. \
Abstain (choice null) when nothing the operator said or wrote supports an answer, or when the \
operator would most likely reply with something other than the offered options (redirect, add a \
condition, ask back). Abstaining is a good answer; a wrong confident answer is a bad one.

Mark "outward": true when the answer would publish, push, deploy, touch production, send a \
message or email, delete, pay, or use a credential — whatever the answer is.

References are checked mechanically and verbatim. An "operator" reference must quote the \
operator's own words from this conversation exactly; a "file" reference must give the path and \
an exact excerpt of that file (use your Read/Grep tools; never quote from memory). A \
"decision" reference is a file excerpt that records the operator's decision. A reference that \
does not check out is discarded and your tier drops to "likely".

Tiers: "decided" — the operator already decided this (quote it); "found" — the answer is \
written in the project's information (cite it); "likely" — inferred, with a confidence 0..1.

Reply with ONE JSON object and nothing else:
{"answers": [{"key": "Q1", "choice": "<one option verbatim, or null>", "tier": "decided|found|likely", \
"confidence": 0.0-1.0, "outward": false, "reason": "<one line>", \
"references": [{"kind": "operator", "quote": "..."}, {"kind": "file|decision", "path": "...", "quote": "..."}]}]}
"""


def build_prompt(kind: str, questions: Sequence[Question], kb_hits: Sequence[Dict[str, str]],
                 locations: Sequence[str], conversation: bool = True) -> str:
    parts = [PROMPT_HEAD]
    if not conversation:
        parts.append("NOTE: you are NOT a fork — there is no conversation; use only the files.\n")
    label = {KIND_CONTINUATION: "The agent finished its turn; the question is what it should do next. "
             "The options are suggestions; a free-text instruction is a valid choice here.",
             KIND_PERMISSION: "The agent asks for permission to run a tool.",
             KIND_ASK: "The agent asked the operator a question with a fixed option list."}.get(kind, "")
    parts.append(f"\nKIND: {kind}. {label}\n")
    for q in questions:
        opts = "\n".join(f"  - {o}" for o in q.options) or "  (no options)"
        multi = " (several options may be chosen: give a list)" if q.multi else ""
        parts.append(f"\n[{q.key}]{multi}\n{q.text}\nOptions:\n{opts}\n")
    if kb_hits:
        parts.append("\nCandidate sections from the project's knowledge base (open them to quote):\n")
        parts += [f"- {h['path']} — {h['heading']}: {h['excerpt']}\n" for h in kb_hits]
    if locations:
        parts.append("\nWhere this operator's decisions are written (read what is relevant):\n")
        parts += [f"- {p}\n" for p in locations]
    return "".join(parts)


# --------------------------------------------------------------------------- #
# the fork, its fallback, and its end (tasks 2.5, 3.4b)
# --------------------------------------------------------------------------- #

FORK_FLAGS = ("-p", "--fork-session", "--no-session-persistence", "--strict-mcp-config",
              "--tools", "Read,Grep,Glob", "--output-format", "json",
              "--settings", json.dumps({"disableAllHooks": True}))


def fork_argv(launch: Launch, session_id: str) -> List[str]:
    return [*launch.argv, "--resume", session_id, *FORK_FLAGS]


def fallback_argv(model: str) -> List[str]:
    return ["claude", "--model", model, *[f for f in FORK_FLAGS if f != "--fork-session"]]


def _kill_group(pgid: int) -> None:
    for sig in (signal.SIGTERM, signal.SIGKILL):
        try:
            os.killpg(pgid, sig)
        except (ProcessLookupError, PermissionError):
            return
        time.sleep(0.2)


def run_bounded(argv: Sequence[str], prompt: str, *, cwd: str, env: Dict[str, str],
                unset: Sequence[str] = (), timeout: float,
                popen: Callable[..., Any] = subprocess.Popen) -> Tuple[Optional[str], str]:
    """Run one non-interactive model call in its OWN process group, and leave nothing behind.

    On the bound the whole group is terminated, so a stuck tool call cannot keep a child
    alive (D12). After a normal exit the group is swept too: a child the run started
    and did not wait for is still the fork's. Returns (stdout or None, reason).

    ⚠ Standard input and output are FILES, not pipes. A pipe is at EOF only when every
    holder has closed it, so a child the fork left running would hold the answer back
    until the bound and turn an answered decision into a timeout — the same trap the
    relay's `_run_command` documents, measured here by a test before it shipped.
    """
    child_env = {k: v for k, v in os.environ.items() if k not in set(unset)}
    child_env.update(env)
    child_env[GUARD_ENV] = "1"
    child_env[WAIT_DETECT_GUARD_ENV] = "1"
    t0 = time.monotonic()
    with tempfile.TemporaryFile("w+", encoding="utf-8") as stdin, \
            tempfile.TemporaryFile("w+", encoding="utf-8") as stdout:
        stdin.write(prompt)
        stdin.flush()
        stdin.seek(0)
        try:
            proc = popen(list(argv), cwd=cwd or None, env=child_env, stdin=stdin, stdout=stdout,
                         stderr=subprocess.DEVNULL, text=True, start_new_session=True)
        except OSError as exc:
            return None, f"could not start ({type(exc).__name__})"
        try:
            proc.wait(timeout=timeout)
        except subprocess.TimeoutExpired:
            _kill_group(proc.pid)
            try:
                proc.wait(timeout=5)
            except subprocess.TimeoutExpired:
                pass
            logger.warning("auto answer: decision timed out after %.0f s; group %s terminated", timeout, proc.pid)
            return None, f"timed out after {timeout:.0f} s"
        finally:
            _kill_group(proc.pid)
        stdout.seek(0)
        out = stdout.read()
    took = time.monotonic() - t0
    if proc.returncode != 0:
        logger.warning("auto answer: decision exited %s after %.1f s", proc.returncode, took)
        return None, f"exited {proc.returncode}"
    logger.info("auto answer: decision returned in %.1f s", took)
    return out, "ok"


def result_text(stdout: Optional[str]) -> Tuple[str, Dict[str, Any]]:
    """`--output-format json` → (the model's text, its usage). A plain reply passes through."""
    if not stdout:
        return "", {}
    try:
        data = json.loads(stdout)
    except ValueError:
        return stdout, {}
    if isinstance(data, dict) and isinstance(data.get("result"), str):
        usage = data.get("usage") if isinstance(data.get("usage"), dict) else {}
        return data["result"], {k: usage.get(k) for k in ("input_tokens", "cache_read_input_tokens",
                                                          "cache_creation_input_tokens", "output_tokens")}
    return stdout, {}


# --------------------------------------------------------------------------- #
# the reference check (task 2.5b)
# --------------------------------------------------------------------------- #

#: A quote shorter than this proves nothing: "igen" occurs in every session.
MIN_QUOTE_CHARS = 8
MAX_FILE_BYTES = 4 << 20
_REMINDER = re.compile(r"<system-reminder>.*?</system-reminder>", re.S)
_INJECTED_PREFIXES = ("<task-notification", "<local-command", "Caveat:", "[Request interrupted")


def normalise(text: str) -> str:
    return re.sub(r"\s+", " ", text or "").strip()


def _epoch(stamp: Any) -> Optional[float]:
    if not isinstance(stamp, str) or not stamp:
        return None
    try:
        return datetime.fromisoformat(stamp.replace("Z", "+00:00")).timestamp()
    except ValueError:
        return None


def operator_turns(path: Optional[Path], before: float) -> List[str]:
    """The operator's own words in the transcript, before `before`, normalised.

    A `user` entry that is not meta, whose content is text (not a tool result), with the
    harness's injected blocks removed: a system reminder, a task notification, a local
    command echo are not something the operator said.
    """
    if path is None:
        return []
    out: List[str] = []
    try:
        handle = path.open("rb")
    except OSError:
        return []
    with handle:
        for line in handle:
            if b'"user"' not in line:
                continue
            try:
                entry = json.loads(line)
            except ValueError:
                continue
            if not isinstance(entry, dict) or entry.get("type") != "user" or entry.get("isMeta"):
                continue
            ts = _epoch(entry.get("timestamp"))
            if ts is None or ts >= before:
                continue
            content = (entry.get("message") or {}).get("content") if isinstance(entry.get("message"), dict) else None
            texts: List[str] = []
            if isinstance(content, str):
                texts = [content]
            elif isinstance(content, list):
                texts = [b.get("text", "") for b in content if isinstance(b, dict) and b.get("type") == "text"]
            for t in texts:
                t = _REMINDER.sub(" ", t).strip()
                if t and not t.startswith(_INJECTED_PREFIXES):
                    out.append(normalise(t))
    return out


def _resolve(path: str, cwd: str) -> Path:
    p = Path(os.path.expanduser(path))
    return p if p.is_absolute() else Path(cwd or "/") / p


def check_references(answer: Answer, turns: Sequence[str], cwd: str) -> Answer:
    """Check every reference verbatim and derive the tier from what checks out."""
    for ref in answer.references:
        quote = normalise(ref.quote)
        if len(quote) < MIN_QUOTE_CHARS:
            ref.checked, ref.reason = False, "too short to prove anything"
            continue
        if ref.kind == "operator":
            ref.checked = any(quote in t for t in turns)
            ref.reason = "" if ref.checked else "not in an operator turn before the question"
            continue
        target = _resolve(ref.path, cwd)
        try:
            if not target.is_file() or target.stat().st_size > MAX_FILE_BYTES:
                ref.checked, ref.reason = False, "no such file, or too large"
                continue
            body = normalise(target.read_text(encoding="utf-8", errors="replace"))
        except OSError:
            ref.checked, ref.reason = False, "unreadable"
            continue
        ref.checked = quote in body
        ref.reason = "" if ref.checked else "excerpt not in the file"
    ok = [r for r in answer.references if r.checked]
    if any(r.kind == "operator" or r.decision for r in ok):
        answer.tier = TIER_DECIDED
    elif ok:
        answer.tier = TIER_FOUND
    else:
        answer.tier = TIER_LIKELY
    return answer


# --------------------------------------------------------------------------- #
# the whole decision
# --------------------------------------------------------------------------- #

@dataclass
class Decision:
    answers: Dict[str, Answer]
    refused: Dict[str, str]
    method: str                   # "fork" | "fallback" | "none"
    notes: List[str] = field(default_factory=list)
    usage: Dict[str, Any] = field(default_factory=dict)
    launch: str = ""


def decide(envelope: Dict[str, Any], *, kind: str, session_id: str, cwd: str, asked_at: float,
           get: Getter = local_config.get,
           kb: Callable[[Sequence[Question], str], Tuple[List[Dict[str, str]], str]] = kb_candidates,
           launch_of: Callable[[str, Optional[Path]], Optional[Launch]] = session_launch,
           transcript: Callable[[str], Optional[Path]] = transcript_of,
           runner: Callable[..., Tuple[Optional[str], str]] = run_bounded) -> Decision:
    """Look it up, fork, check. Never raises: a failure is a Decision with no answers."""
    questions = questions_of(envelope)
    if not questions:
        return Decision({}, {}, "none", ["no questions in the envelope"])
    notes: List[str] = []
    hits, kb_note = kb(questions, cwd)
    notes.append(kb_note)
    path = transcript(session_id) if session_id else None
    launch = launch_of(session_id, path) if path else None
    locations = decision_locations(cwd, extra_paths(get))
    bound = decide_timeout_s(get)
    if launch is not None:
        method = "fork"
        prompt = build_prompt(kind, questions, hits, locations, conversation=True)
        out, reason = runner(fork_argv(launch, session_id), prompt, cwd=cwd, env=launch.env,
                             unset=launch.unset, timeout=bound)
        notes.append(f"fork on {launch.describe()}: {reason}")
    else:
        method = "fallback"
        notes.append("fallback: sources-only (" + ("no transcript" if path is None else
                                                    "the session's provider could not be placed") + ")")
        prompt = build_prompt(kind, questions, hits, locations, conversation=False)
        out, reason = runner(fallback_argv(fallback_model(get)), prompt, cwd=cwd, env={}, unset=(),
                             timeout=bound)
        notes.append(f"fallback: {reason}")
    if out is None:
        return Decision({}, {q.key: reason for q in questions}, method, notes,
                        launch=launch.describe() if launch else "")
    text, usage = result_text(out)
    answers, refused = parse_decision(text, questions, kind)
    turns = operator_turns(path, asked_at) if method == "fork" else []
    for a in answers.values():
        check_references(a, turns, cwd)
    logger.info("auto answer [%s]: %s — %d answered, %d refused (%s)", (session_id or "?")[:8], method,
                len(answers), len(refused), "; ".join(sorted(set(refused.values()))) or "-")
    return Decision(answers, refused, method, notes, usage, launch.describe() if launch else "")
