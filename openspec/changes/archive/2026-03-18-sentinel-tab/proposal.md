# Proposal: sentinel-tab

## Why

The sentinel supervisor runs in a separate terminal (Zed, iTerm, tmux) and has no communication channel with wt-web. Users cannot see sentinel decisions, findings, or assessments from the dashboard, and cannot send messages to the sentinel without switching terminals. This creates a blind spot in orchestration monitoring.

## What Changes

- **New Python sentinel library** (`lib/set_orch/sentinel/`) for structured event logging, findings management, inbox polling, status tracking, and run rotation
- **New CLI wrappers** for the library (usable from both bash and agent sentinel modes)
- **New `.wt/sentinel/` runtime directory** with events.jsonl, findings.json, status.json, and archive/
- **Modified bash sentinel** (`bin/set-sentinel`) to emit structured events and check inbox every 5s
- **Modified agent sentinel skill** to use event logging, findings, and 3s inbox polling
- **New wt-web Sentinel tab** with event stream, findings panel, assessment section, and message input
- **New wt-web backend endpoints** for sentinel events, findings, status, and messaging
- **`.gitignore` entry** for `/.set/` directory

## Capabilities

### New Capabilities
- `sentinel-events` — structured event logging to `.wt/sentinel/events.jsonl`
- `sentinel-findings` — bug/observation/assessment tracking in `.wt/sentinel/findings.json`
- `sentinel-messaging` — bidirectional user↔sentinel communication with 3-5s latency
- `sentinel-dashboard` — wt-web tab showing event stream, findings, and message input

### Modified Capabilities
_(none — existing sentinel behavior is preserved, new structured output is additive)_

## Impact

- **Python modules**: new `lib/set_orch/sentinel/` package (events, findings, inbox, status, rotation)
- **Bash**: `bin/set-sentinel` modified to call sentinel CLI tools
- **Agent skill**: `.claude/commands/wt/sentinel.md` updated with event logging and inbox instructions
- **wt-web backend**: new REST endpoints in `lib/set_orch/api.py`
- **wt-web frontend**: new `SentinelPanel.tsx` component + tab in Dashboard
- **Filesystem**: new `.wt/` directory convention (gitignored)
- **Dependencies**: none new (uses existing Python stdlib, FastAPI, React)
