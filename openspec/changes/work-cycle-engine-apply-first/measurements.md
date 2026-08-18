# Measurements — group 2, taken before committing to reuse

Written by the run that implemented tasks 2.1 and 2.2. It exists as a separate artifact
because `task-group-resolution` requires a later run's reading list to include artifacts
earlier runs produced: the verdicts below are what group 4 builds on, and a verdict without
its evidence is the thing this repository's rules refuse.

Every figure names the command or the `file:line` that produced it.

---

## 2.1 — Can `GatePipeline` be pointed at one tree and a subset of gates?

`lib/set_orch/gate_runner.py:216`.

### The half that works, and needed no change

- **One tree.** The pipeline reads the working tree from exactly one place —
  `self.change.worktree_path`, 11 occurrences, no other source
  (`grep -oE "self\.change\.[a-z_]+" lib/set_orch/gate_runner.py | sort | uniq -c`). So D3
  holds: a caller supplies a worktree or a repository root by setting that field, and the
  pipeline cannot tell the difference.
- **A subset of gates.** `GateConfig(gates={"test": "run"})` plus registering only the wanted
  gates is sufficient; `run()` skips anything `gc.should_run()` refuses
  (`gate_runner.py:690`). Measured on a scratch repository: exactly one gate executed.
- **The three behaviours the design feared are inert on a first run.** `_try_cache_reuse`
  (`:449`) and `_try_scoped_run` (`:505`) both return `None` immediately while
  `change.verify_retry_index == 0`, and `_diff_has_new_api_surface` is reachable *only* from
  inside `_try_cache_reuse`. So retry caching, cache-scope diff and new-API-surface detection
  are **not** the obstacle — the open question named the wrong three suspects.

### The half that does not, measured end to end

The pipeline writes **orchestration state** — 9 `update_change_field()` call sites inside
`GatePipeline`, none of them optional:

| line | field | when |
|---|---|---|
| `:673` | `last_gate_commit` | start of every `run()` |
| `:849`–`:856` | `<gate>_result`, `<gate>_ms`, `<gate>_output` | after every gate |
| `:1017` | the gate's own retry counter | on a blocking failure with budget left |
| `:1023` | `verify_retry_count` | ditto |
| `:1028` | `status = "verify-failed"` | ditto |
| `:1033` | `retry_context` | ditto |
| `:1064` | `status = "failed"` | on a blocking failure with retries exhausted |

A probe on a scratch git repository with one deliberately failing gate, `max_retries=0`:

```
ACTION: failed
STATE AFTER: {"name": "probe", "status": "failed", "test_result": "fail",
              "test_output": "boom", "last_gate_commit": "c6a37b8e…"}
```

**The fail direction is what decides this.** A *section* gate going red would leave the whole
*change* recorded as `status: "failed"` — one slice's failure presented as the change having
failed verification. That is the merge semantics the question was about, and it is on the
unconditional failure path, not behind a flag.

The escape — pointing `state_file` at a scratch file — is refused rather than unavailable: it
would be a second store of run state, and `work-cycle-control` requires exactly one place run
state comes from. The state file must also be orchestration's own schema; a `changes` object
instead of an array raises `StateCorruptionError` (`state.py:562`), measured.

### Verdict — outcome (b) of the two the design allowed

**Run the resolved gate steps directly; do not reuse `GatePipeline`.** The gate *configuration*
source stays fixed as the design requires: `resolve_gate_config(change, profile, directives,
tree)` (`gate_profiles.py:240`), the same six-layer chain the merge path uses.

Reusable as-is, because an AST scan shows they write no state at all —
`GateResult`, `GateDefinition`, `_resolve_gate_order`, `_truncate_gate_output`. The state
coupling is confined to `GatePipeline` itself.

---

## 2.2 — What of the stream consumption in `chat.py` is reusable outside a websocket?

`lib/set_orch/chat.py`, 513 lines.

### Extractable

- **`_map_event`** (`:250`, 41 lines) is pure: `dict` in, `dict` out, no session state, no
  socket. Its one `WebSocket` mention is in the docstring — a substring scan calls it coupled
  and is wrong. Reusable as a *shape*; its output vocabulary (`assistant_text`, `tool_use`,
  `tool_result`, `assistant_done`) is the chat protocol and is re-expressed, not adopted.
- **The invocation shape** from `_build_claude_cmd` (`:81`, 26 lines):
  `claude -p --output-format stream-json --verbose --model <resolved>`, with
  `resolve_model_id` from `subprocess_utils`. Chat-specific and not carried over:
  `--append-system-prompt build_chat_context(...)`, `--resume`, `--permission-mode auto`.
- **The `system`/`init` event carrying `session_id`** (`:181`–`:186`). This answers the
  design's third Open Question — *where a session-scoped seat comes from in a headless run*.
  It comes from the agent process the engine itself starts, on the first event of its own
  stream. It is read, never invented, which is what D9 requires.

### Re-expressed, not extracted

- **The async framing.** `_run_claude` (`:123`, 126 lines) is built on
  `asyncio.create_subprocess_exec` and `async for line in proc.stdout` (14 `asyncio`
  references in the file). The engine's entry point is a synchronous command with no running
  service (`work-cycle-control`), so this becomes `subprocess.Popen(..., stdout=PIPE)` with a
  blocking line loop. The *mechanic* inside is small — read a line, strip it, `json.loads`,
  skip a non-JSON line with a debug log rather than dying, dispatch. The other ~100 lines are
  chat's: `await self._broadcast(...)` to a `set[WebSocket]`, the generation/reset guard, the
  message-history accumulation, and the stale-session retry.

### The measured negative, which is the more useful half

**`chat.py` is the only live stream consumer in this framework.** `grep -rln "stream-json"`
returns **7** files; six of them do not consume a stream:

- `manager/supervisor.py:250,289,339`, `issues/fixer.py:122`, `issues/investigator.py:103` —
  redirect the process's stdout to a **file**. `investigator.py` then reads only the *first*
  line, to lift `session_id` (`:119`–`:137`).
- `manager/api.py:209`, `api/sentinel.py:146` — `for line in content.splitlines()` over
  already-complete content.
- `api/status_follow.py` — iterates no process output at all.

So there was no synchronous consumer to adopt, and the grep's count overstated the corpus by
six. It is the repository's own rule about a hit being a proxy for a behaviour, met while
answering a question about reuse: **the first search said "six other places already do this",
and reading them said none of them do.**
