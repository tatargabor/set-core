"""Running one work unit as a full agent session, and watching it while it runs.

Two properties are requirements rather than implementation choices.

**A full session, not a subagent.** Hooks, rule injection and gates apply to an agent session
the way they apply to an interactive run; a subagent inherits a different, quieter world. A
unit that runs under different rules than the ones the project enforces is not testing the
project's rules.

**Streamed, not awaited.** Waiting for a final message makes a running unit invisible: there
is no difference, from outside, between working and hung. The events are consumed as they
arrive, and the first of them carries the session id — which is where a headless run's
session-scoped seat comes from. It is read off the process the engine itself started, never
invented.

Measured before it was written (task 2.2): the framework's only live stream consumer is the
websocket chat path. Six other files match "stream-json" and none of them consume a stream —
five redirect stdout to a file, two parse already-complete content. So the async framing was
re-expressed as a blocking loop rather than extracted, and the mechanic that survived is
small: read a line, parse it, skip a non-JSON line with a log instead of dying, dispatch.
"""

from __future__ import annotations

import json
import logging
import os
import subprocess
from dataclasses import dataclass, field
from pathlib import Path
from typing import Callable, Iterable, Iterator, Optional, Sequence

logger = logging.getLogger(__name__)

__all__ = [
    "AgentRun", "AgentEvent", "StreamSink", "build_agent_command", "run_agent_session",
    "iter_events",
]


@dataclass(frozen=True)
class AgentEvent:
    """One event off the session's stream, kept raw alongside what the engine reads."""

    type: str
    subtype: str = ""
    payload: dict = field(default_factory=dict)

    @property
    def session_id(self) -> str:
        return str(self.payload.get("session_id") or "")


@dataclass
class AgentRun:
    """What one session produced: its id, its final text, and how it ended."""

    session_id: str = ""
    final_text: str = ""
    exit_code: Optional[int] = None
    events: int = 0
    stderr: str = ""


class StreamSink:
    """The session's stream, written down as it arrives.

    Three properties, each of which is a requirement rather than a convenience:

    **Incremental.** Every event is written and flushed as it lands. A run killed
    mid-way keeps everything it had produced — and a killed run is precisely the
    one somebody wants to read, so buffering it into a final write would lose it
    exactly when it matters.

    **Terminated.** A completed stream ends with a marker line. Without one a
    truncated file and a finished one are indistinguishable, and a reader has no
    way to tell "this is all there was" from "this is all that survived".

    **Located by the caller.** The path is built from the tree the engine was
    given, never from anything this module decides. The stream carries the
    project's own domain — partner names, order numbers, whatever the work is
    about — so it lives in the project's runtime area and the framework persists
    none of it. See External Project Confidentiality.
    """

    #: The last line of a stream that ended on its own.
    TERMINATOR = "__stream_end__"

    def __init__(self, path: Path):
        self.path = Path(path)
        self.events = 0
        self._fh = None

    def open(self) -> "StreamSink":
        self.path.parent.mkdir(parents=True, exist_ok=True)
        # Opened BEFORE the session starts, so an empty file means "a session ran
        # and said nothing" while no file at all means "no session was started".
        # Those are different facts and a reader must not have to guess which.
        self._fh = self.path.open("w", encoding="utf-8")
        return self

    def write(self, event: "AgentEvent") -> None:
        if self._fh is None:
            return
        try:
            self._fh.write(json.dumps(event.payload, ensure_ascii=False) + "\n")
            self._fh.flush()
        except (OSError, TypeError, ValueError) as exc:
            # Named, never swallowed — but a sink that cannot write must not end a
            # run that is otherwise working. The record will say how many events
            # reached it, so the loss is visible rather than silent.
            logger.warning("work unit: could not write to the run stream: %s", exc)
        else:
            self.events += 1

    def close(self, *, exit_code=None) -> None:
        if self._fh is None:
            return
        try:
            self._fh.write(json.dumps({
                "type": self.TERMINATOR, "events": self.events, "exit_code": exit_code,
            }) + "\n")
            self._fh.flush()
        except OSError as exc:
            logger.warning("work unit: could not terminate the run stream: %s", exc)
        finally:
            try:
                self._fh.close()
            finally:
                self._fh = None

    def __enter__(self) -> "StreamSink":
        return self.open()

    def __exit__(self, exc_type, exc, tb) -> None:
        self.close()


def build_agent_command(
    prompt: str, *, model: Optional[str] = None, extra_args: Sequence[str] = (),
) -> list[str]:
    """The invocation shape, taken from the framework's existing consumer.

    Chat's own flags are deliberately absent: no `--append-system-prompt` built from a chat
    context, no `--resume`, no permission mode chosen on the session's behalf. A work unit
    runs with the project's own hooks and rules, which is what "a full session" means.
    """
    cmd = ["claude", "-p", "--output-format", "stream-json", "--verbose"]
    if model:
        try:
            from set_orch.subprocess_utils import resolve_model_id

            cmd += ["--model", resolve_model_id(model)]
        except Exception:  # pragma: no cover - the resolver is optional here
            cmd += ["--model", model]
    cmd += list(extra_args)
    cmd += ["--", prompt]
    return cmd


def iter_events(lines: Iterable[str]) -> Iterator[AgentEvent]:
    """Parse a stream-json line sequence. A non-JSON line is logged and skipped.

    Skipped rather than fatal on purpose: a CLI that prints one diagnostic line to stdout
    must not end a unit that is otherwise working.
    """
    for raw in lines:
        line = raw.strip()
        if not line:
            continue
        try:
            payload = json.loads(line)
        except json.JSONDecodeError:
            # ⚠ The SHAPE, never the content. This logged up to 200 characters of
            # the line until 2026-08-29, and a line off a consumer's session is
            # full of that consumer's domain — so a DEBUG log became a place the
            # framework persisted a customer's data. The same rule `db_safety.py`
            # follows for URLs: enough to debug with, nothing to leak.
            logger.debug(
                "non-JSON line on the agent stream: %d chars, starts %r",
                len(line), line[:1],
            )
            continue
        if not isinstance(payload, dict):
            continue
        yield AgentEvent(
            type=str(payload.get("type", "")),
            subtype=str(payload.get("subtype", "")),
            payload=payload,
        )


def run_agent_session(
    prompt: str,
    cwd: str | Path,
    *,
    model: Optional[str] = None,
    extra_args: Sequence[str] = (),
    on_event: Optional[Callable[[AgentEvent], None]] = None,
    timeout: Optional[float] = None,
) -> AgentRun:
    """Run one unit as a full agent session in `cwd`, consuming its stream as it goes."""
    cmd = build_agent_command(prompt, model=model, extra_args=extra_args)
    env = {**os.environ}
    # Nested-session protection would refuse the child; the engine is deliberately starting
    # a full session, which is the thing that variable exists to prevent by accident.
    env.pop("CLAUDECODE", None)

    logger.info("work unit: spawning agent session in %s", cwd)
    proc = subprocess.Popen(
        cmd, cwd=str(cwd), env=env,
        stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, bufsize=1,
    )
    run = AgentRun()
    assert proc.stdout is not None
    try:
        for event in iter_events(proc.stdout):
            run.events += 1
            if event.type == "system" and event.subtype == "init" and event.session_id:
                run.session_id = event.session_id
                logger.info("work unit: session id %s", run.session_id)
            elif event.type == "result":
                run.final_text = str(event.payload.get("result") or "")
            if on_event is not None:
                on_event(event)
        proc.wait(timeout=timeout)
    except subprocess.TimeoutExpired:
        logger.error("work unit: agent session timed out after %ss — killing", timeout)
        proc.kill()
        proc.wait()
    run.exit_code = proc.returncode
    if proc.stderr is not None:
        run.stderr = proc.stderr.read()[-4000:]
    logger.info(
        "work unit: session ended exit=%s events=%d session=%s",
        run.exit_code, run.events, run.session_id or "(none)",
    )
    return run
