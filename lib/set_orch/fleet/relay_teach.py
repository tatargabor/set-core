"""Teach a project rule from the question relay (fleet-relay-teach).

The owner asked (2026-11-24) for a way to answer a waiting question once AND teach the system
the answer for next time, with a short explanation or condition, collected per project and
committed so a teammate works the same way. A taught rule lands in the asking project's
`.claude/rules/auto-answer-taught.md`:

- every Claude Code session in that project loads `.claude/rules/`, so an agent that has the
  rule stops asking;
- the auto-answer decider reads the file verbatim, and a checked quote from it backs a
  `decided` answer that no outward-step exclusion blocks (the owner's choice, „Mindig mehet");
- a permission prompt is never taught or answered this way.

The file is written in the repository's MAIN worktree and committed alone with a pathspec
commit, the project's own hooks running, never pushed (design D2, D3). The rule's text is the
project's content: it is written into the project and NEVER into set-core's logs.
"""
from __future__ import annotations

import datetime as _dt
import logging
import re
import subprocess
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional

from . import question_relay as qr

logger = logging.getLogger(__name__)

RULES_REL = Path(".claude") / "rules" / "auto-answer-taught.md"

HEADER = """# Taught answers — rules the operator taught from the question relay

Every agent session in this project loads this file. Each entry is a question an agent asked,
the answer the operator taught for it, and — when given — the condition or reason. Apply an
entry only when its condition holds; otherwise ask as usual. The auto-answer decider reads this
file too and answers such a question on the operator's behalf. Edit or delete entries here by
hand; new ones are appended from the fleet's question-relay panel.
"""

_GIT_TIMEOUT_S = 30
_LOCK_RETRIES = 5
_LOCK_WAIT_S = 0.4


def _git(args: List[str], cwd: Path, timeout: float = _GIT_TIMEOUT_S) -> subprocess.CompletedProcess:
    return subprocess.run(["git", *args], cwd=str(cwd), capture_output=True, text=True, timeout=timeout)


def main_checkout(cwd: str) -> Any:
    """The main worktree of the repository holding `cwd`, as a Path, or the reason (str)."""
    if not cwd or not Path(cwd).is_dir():
        return "the agent's working directory is not on this machine"
    try:
        out = _git(["worktree", "list", "--porcelain"], Path(cwd))
    except (OSError, subprocess.SubprocessError) as exc:
        logger.warning("relay teach: git worktree list failed (%s)", type(exc).__name__)
        return "git could not be run"
    if out.returncode != 0:
        return "the agent's working directory is not inside a git repository"
    for line in out.stdout.splitlines():
        if line.startswith("worktree "):
            root = Path(line[len("worktree "):].strip())
            if root.is_dir():
                return root
            break
    return "the repository's main worktree could not be found"


def rules_path(root: Path) -> Path:
    return root / RULES_REL


def _heading(question: str) -> str:
    first = next((ln.strip() for ln in (question or "").splitlines() if ln.strip()), "Taught answer")
    first = re.sub(r"^[#>*\-\s]+", "", first)
    return first if len(first) <= 90 else first[:87].rstrip() + "…"


def _quoted(text: str) -> str:
    """A multi-line value as an indented block, so it stays inside its bullet."""
    lines = (text or "").strip().splitlines() or [""]
    return lines[0] + "".join("\n  " + ln for ln in lines[1:])


def entry_text(question: str, answer: str, explanation: str, today: str) -> str:
    parts = [f"## {_heading(question)}", "", f"- **Question:** {_quoted(question)}",
             f"- **Answer:** {_quoted(answer)}"]
    if explanation and explanation.strip():
        parts.append(f"- **When / why:** {_quoted(explanation)}")
    parts.append(f"- *Taught {today} from the question relay.*")
    return "\n".join(parts) + "\n"


def append_rule(root: Path, question: str, answer: str, explanation: str, today: str) -> Path:
    """Append one entry; create the file with its header when missing. Earlier entries are
    never rewritten — the append goes through an `a` open, not a read-modify-write."""
    path = rules_path(root)
    path.parent.mkdir(parents=True, exist_ok=True)
    if not path.exists():
        path.write_text(HEADER, encoding="utf-8")
    with path.open("a", encoding="utf-8") as fh:
        fh.write("\n" + entry_text(question, answer, explanation, today))
    return path


@dataclass
class CommitResult:
    sha: str = ""
    branch: str = ""
    reason: str = ""


def _short(text: str, limit: int = 300) -> str:
    text = " ".join((text or "").split())
    return text if len(text) <= limit else text[:limit - 1] + "…"


def commit_rule(root: Path, path: Path, today: str) -> CommitResult:
    """Commit the one file, alone: `git commit -- <file>` takes only that path, so another
    session's staged work stays staged. Hooks run; a refusal is reported, never bypassed."""
    rel = str(path.relative_to(root))
    try:
        head = _git(["symbolic-ref", "--quiet", "--short", "HEAD"], root)
        if head.returncode != 0:
            return CommitResult(reason="the main checkout is on a detached HEAD; the rule is written but not committed")
        branch = head.stdout.strip()
        for attempt in range(_LOCK_RETRIES):
            add = _git(["add", "--", rel], root)
            out = add if add.returncode != 0 else _git(
                ["commit", "-q", "-m", f"auto-answer: taught rule {today}", "--", rel], root, timeout=120)
            err = (out.stderr or "") + (out.stdout or "")
            if out.returncode == 0:
                sha = _git(["rev-parse", "--short", "HEAD"], root).stdout.strip()
                return CommitResult(sha=sha, branch=branch)
            if "index.lock" in err and attempt < _LOCK_RETRIES - 1:
                time.sleep(_LOCK_WAIT_S)
                continue
            return CommitResult(branch=branch, reason="the commit was refused: " + (_short(err) or f"exit {out.returncode}"))
    except (OSError, subprocess.SubprocessError) as exc:
        logger.warning("relay teach: git failed (%s)", type(exc).__name__)
        return CommitResult(reason=f"git could not be run ({type(exc).__name__})")
    return CommitResult(reason="the index stayed locked by another git process")


@dataclass
class TeachResult:
    answered: bool = False
    answer_reason: str = ""
    written: bool = False
    rules_file: str = ""
    project: str = ""
    commit: CommitResult = field(default_factory=CommitResult)

    def as_dict(self) -> Dict[str, Any]:
        return {"answered": self.answered, "answer_reason": self.answer_reason,
                "written": self.written, "rules_file": self.rules_file, "project": self.project,
                "commit": {"sha": self.commit.sha, "branch": self.commit.branch, "reason": self.commit.reason}}


def teachable(waiting: Optional[Dict[str, Any]]) -> Optional[str]:
    """Why this waiting call cannot be taught, or None."""
    if not waiting:
        return "the question is no longer waiting on the relay"
    if (waiting.get("kind") or "question") == "permission":
        return "a permission prompt is answered only by a person"
    if int(waiting.get("questions") or 0) != 1:
        return "the agent asked several questions at once; answer them in its terminal"
    return None


def find_waiting(call_id: str, base: Optional[Path] = None) -> Optional[Dict[str, Any]]:
    return next((r for r in qr.list_waiting(base) if r.get("id") == call_id), None)


def teach(call_id: str, answer: str, explanation: str, *, question: str, cwd: str,
          waiting: Optional[Dict[str, Any]], base: Optional[Path] = None,
          today: Optional[str] = None) -> TeachResult:
    """Answer the call first (the agent waiting is the cost being paid), then write and commit
    the rule. Each step reports on its own; neither undoes the other (design D4)."""
    today = today or _dt.date.today().isoformat()
    res = TeachResult()
    answer = (answer or "").strip()
    if not answer:
        res.answer_reason = "the answer is empty"
        return res
    if waiting and (waiting.get("kind") or "question") == "permission":
        res.answer_reason = "a permission prompt is answered only by a person"
        return res
    if waiting is None:
        res.answer_reason = "the question was no longer waiting, so nothing was answered"
    elif int(waiting.get("questions") or 0) != 1:
        res.answer_reason = "the agent asked several questions at once; answer them in its terminal"
        return res
    else:
        why = qr.deliver_answer(str(waiting.get("session_id") or ""), answer, base)
        res.answered, res.answer_reason = why is None, why or ""

    root = main_checkout(cwd)
    if isinstance(root, str):
        res.commit = CommitResult(reason=root + "; the rule was not written")
        logger.warning("relay teach [%s]: rule not written (%s)", qr._safe_id(call_id)[-12:], root)
        return res
    path = append_rule(root, question, answer, explanation, today)
    res.written, res.rules_file, res.project = True, str(RULES_REL), root.name
    res.commit = commit_rule(root, path, today)
    logger.info("relay teach [%s]: rule appended to %s in %s; answered=%s commit=%s%s",
                qr._safe_id(call_id)[-12:], RULES_REL, root.name, res.answered,
                res.commit.sha or "none", f" ({res.commit.branch})" if res.commit.branch else "")
    if res.commit.reason:
        logger.warning("relay teach [%s]: not committed in %s: %s", qr._safe_id(call_id)[-12:],
                       root.name, res.commit.reason[:120])
    return res
