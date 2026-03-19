## Context

The Control Center GUI currently displays usage for a single Claude account via `UsageWorker`, which reads one session key from `~/.config/set-core/claude-session.json`. The `DualStripeBar` widget renders two stacked stripes (time elapsed + usage consumed) for each time window (5h/7d). Users with multiple Anthropic accounts must manually check each account in the browser.

The existing architecture: `UsageWorker` (single QThread) → `_load_session()` → one API fetch → `usage_updated` signal → `update_usage_bars()` → two `DualStripeBar` widgets (5h + 7d).

## Goals / Non-Goals

**Goals:**
- Display N accounts' usage bars stacked vertically, each with name + 5h bar + 7d bar
- Backward-compatible session file format (old single-key auto-migrates)
- Add/remove accounts via menu dialogs
- Single-account mode looks identical to current UI (no name label)

**Non-Goals:**
- Chrome cookie auto-extraction (investigated, v11 encryption makes this fragile)
- Browser extension or bookmarklet approach
- API key / Admin API support (this is about claude.ai consumer accounts)
- Automatic account discovery

## Decisions

### D1: Session file format evolution

Old: `{"sessionKey": "sk-ant-..."}`
New: `{"accounts": [{"name": "Personal", "sessionKey": "sk-ant-..."}, ...]}`

On read, if `accounts` key is missing but `sessionKey` exists, auto-wrap into `{"accounts": [{"name": "Default", "sessionKey": "..."}]}`. On write, always use the new format. This is a one-way migration — the old format is never written back.

Alternative: separate files per account — rejected because it complicates atomic read/write and the data is tiny.

### D2: UsageWorker emits list instead of dict

Current signal: `usage_updated = Signal(dict)` → single account data.
New signal: `usage_updated = Signal(list)` → list of per-account dicts, each with `name` + existing fields.

The worker iterates accounts sequentially (not threading within thread — accounts are few, each API call is ~1s with timeout). Total cycle stays under 30s for up to 10 accounts.

Alternative: one worker per account — rejected, unnecessary complexity for <10 accounts.

### D3: Dynamic usage row layout

Replace the static `usage_5h_bar`/`usage_7d_bar` pair with a `QVBoxLayout` container (`self.usage_container`) holding N rows. Each row is a `QHBoxLayout` with: `QLabel(name)` + `QLabel(5h_text)` + `DualStripeBar(5h)` + `QLabel(7d_text)` + `DualStripeBar(7d)`.

Rows are created/destroyed dynamically in `update_usage_bars()` when account count changes. Widget references stored in `self.account_widgets: list[dict]`.

When exactly 1 account: hide the name label (identical to current UI).
When 0 accounts: show single row with local-only fallback (current behavior).

### D4: Menu actions for account management

Replace "Set Session Key..." with:
- "Add Account..." → name + session key input dialog
- "Remove Account..." → list selection dialog (only if >1 account)
- Keep "View Usage on claude.ai" unchanged

## Risks / Trade-offs

- **[API rate limiting]** → Fetching N accounts every 30s means N API calls per cycle. Mitigation: 30s interval is already conservative; even 5 accounts = 5 calls/30s, well within reasonable limits.
- **[Window height growth]** → Each account adds ~12px (10px bar + 2px spacing). Mitigation: acceptable for <10 accounts; excessive accounts are an edge case.
- **[Session key expiry]** → Keys may expire at different times. Mitigation: per-account error handling — failed accounts show "--" without affecting others.
