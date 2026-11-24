# Bringing a second machine up to the fleet

How to make another machine run what the fleet does here: the dashboard and agent owner,
the bus, the question relay with the auto-answer in front of it, the desk, the idle-close,
and the automatic clear + handoff. Every step names the check that proves it worked —
a step whose check you did not run is not done.

The order matters: the bus and the handoff package must exist before `set-project init`
runs in a project, because init wires both into it.

## 1. Clone the public repositories

```bash
git clone https://github.com/tatargabor/set-core.git
git clone https://github.com/tatargabor/set-agent-comm.git
git clone https://github.com/tatargabor/set-claude-handoff.git
git clone https://github.com/tatargabor/set-copilot.git     # only for dictation / meeting capture
```

Updating later is `git pull` in each, then step 2 again in set-core. The web bundle
(`web/dist`) is committed, so a pull is enough for the screen — no `pnpm build` needed.

## 2. Install set-core

```bash
cd set-core && ./install.sh
```

This links every `set-*` CLI into `~/.local/bin` and places three systemd user units:
`set-web` (the dashboard, http://localhost:7400), `set-agent-owner` (holds the terminals of
agents started from the fleet) and `set-fleet-idle-close.timer` (daily close of long-idle
agents).

**Check:** `systemctl --user is-active set-web set-agent-owner set-fleet-idle-close.timer`
prints `active` three times, and http://localhost:7400 shows the fleet.

## 3. The bus (`sac`), once per machine

```bash
cd set-agent-comm && npm install && npm install -g .
sac setup          # the launcher the portable hook line in each project finds
```

**Check:** `sac agents` lists this machine's sessions without an error.

## 4. Register the handoff package, then every project

`set-project init` takes the auto-clear templates from the **registered** set-claude-handoff
checkout, so that one goes first:

```bash
cd set-claude-handoff && set-project init --dry-run    # read the plan
set-project init
cd <each project> && set-project init --dry-run && set-project init
```

Init deploys, per project: the base hooks (including `set-hook-question-relay` and
`set-hook-wait-detect`), the MCP registration, and the project's `<name>-auto-clear.service`
watcher. The rest of the relay — the notify, permission and continue hooks — is wired by a
separate step, and the git-side leak gate by another:

```bash
set-relay-wire --registered --dry-run && set-relay-wire --registered
cd <each project> && set-leakscan --install-hooks     # pre-commit, commit-msg, pre-push
```

**Check:** `set-doctor` — every project green, or every warning understood. After an
init, restart open sessions in that project (or `/resume`): hooks load at session start.

## 5. The question relay (machine-local, off by default)

The relay hands a session's `AskUserQuestion`, permission prompt or wait to a channel the
operator reads away from the terminal. The outbound is **this machine's own command**: it
receives a JSON envelope on stdin and the answer comes back as files — the contract is
`openspec/specs/agent-question-relay/spec.md`. The outbound used on the reference machine
is part of a private repository and is not shipped; another machine plugs in its own.

```bash
set-config set question_relay.target command
set-config set question_relay.command "<your two-way outbound>"
set-config set question_relay.notify_command "<optional one-way notifier>"
set-config set question_relay.audience "<who the channel is for>"
set-config set question_relay.enabled true
```

An incomplete configuration is reported, never guessed — with `enabled` on and a key
missing, the hook releases the question to the terminal and says why.

**Check:** the fleet header's relay switch reads on, and a test question from any session
arrives in the channel and its answer reaches the session.

## 6. The auto-answer, in front of the relay

The auto-answer sits between the relay and the operator's outbound: it forks the asking
session, checks the sources it cites, sends the question **with** a proposal, and writes an
allowed answer after a window unless a human answered first. Outward steps and permission
prompts are never written by it.

```bash
set-config set auto_answer.forward_command "<the value question_relay.command had>"
set-config set question_relay.command set-auto-answer
set-config set auto_answer.enabled true        # off = forwards every envelope unchanged
```

Optional tuning, all with defaults: `auto_answer.window_s` (60), `auto_answer.likely_min`
(0.8), `auto_answer.decide_timeout_s` (120), `auto_answer.never_patterns`,
`auto_answer.extra_paths`, `auto_answer.log_days` (90), `auto_answer.model` (the
sources-only fallback's model; a fork always keeps the session's own). The full list with
its meaning is the docstring at the top of `bin/set-auto-answer`.

**Check:** the fleet header's 🤖 panel shows the switch on; the decisions land in
`~/.local/share/set-core/auto-answer/decisions.jsonl`, the log in
`~/.local/share/set-core/question-relay/auto-answer.log`.

## 7. Desk and idle-close thresholds

```bash
set-config set fleet_desk_quiet_minutes 5    # a desk with nothing left to do is closed after this
set-config set fleet_idle_close_hours 48     # the daily timer closes agents idle longer than this
```

Both are optional; the defaults are 5 minutes and 48 hours.

## What does NOT travel

- Machine-local config (`~/.config/set-core/`): the relay outbound, provider keys
  (`providers.json`), the leak-scan deny list. Each machine writes its own.
- Session history, the bus store and the decision log stay on the machine that made them.
- Private repositories are cloned only by whoever has access to them; nothing in the public
  ones depends on them.
