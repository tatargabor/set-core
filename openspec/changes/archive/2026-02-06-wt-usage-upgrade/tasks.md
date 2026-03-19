## 1. Cleanup: Remove old dependencies

- [x] 1.1 Remove `cloudscraper` and `browser_cookie3` from `gui/requirements.txt`
- [x] 1.2 Delete `gui/dialogs/claude_login.py`
- [x] 1.3 Remove all imports/references to `ClaudeLoginDialog` from GUI code (handlers, menu_builder, etc.)
- [x] 1.4 Run `pip uninstall claude-monitor` to remove the redundant package

## 2. UsageCalculator: cost estimation + model tracking

- [x] 2.1 Add per-model token price dict to `gui/usage_calculator.py` (opus, sonnet, haiku)
- [x] 2.2 Extend `parse_usage_line()` to also return the model name
- [x] 2.3 Add `estimate_cost()` method that calculates USD cost from per-model token counts
- [x] 2.4 Add `estimated_cost_usd` field to `get_usage_summary()` return dict

## 3. UsageWorker: replace cloudscraper with urllib

- [x] 3.1 Rewrite `fetch_claude_api_usage()` to use `urllib.request` instead of `cloudscraper`
- [x] 3.2 Add `curl` subprocess fallback if `urllib` gets Cloudflare-blocked
- [x] 3.3 Remove `_import_browser_session()` method (no more browser_cookie3)
- [x] 3.4 Keep `_load_session()` to read from `claude-session.json` only

## 4. GUI: session key input dialog

- [x] 4.1 Add "Set Session Key..." menu action that opens `QInputDialog.getText()`
- [x] 4.2 Save entered key to `~/.config/set-core/claude-session.json`
- [x] 4.3 Test the key with an API call and show success/failure feedback
- [x] 4.4 Remove old "Login to Claude" / "Usage (Browser)" menu items referencing WebEngine

## 5. wt-usage CLI upgrade

- [x] 5.1 Add `--today`, `--week`, `--month` flags using `calculate_usage(since=...)`
- [x] 5.2 Add `--cost` flag that includes estimated cost in output
- [x] 5.3 Add `--login` flag: opens browser via `open`/`xdg-open`, prompts for sessionKey paste, saves + tests it
- [x] 5.4 Improve `--format text` output: aligned columns, thousands separators, header line
- [x] 5.5 When sessionKey available, show exact session/weekly percentages and reset times

## 6. Testing

- [x] 6.1 Add/update GUI tests for session key dialog in `tests/gui/`
- [x] 6.2 Run GUI tests: `PYTHONPATH=. python -m pytest tests/gui/ -v --tb=short`
- [x] 6.3 Fix any failing tests before marking done

## 7. Bug fixes: usage display and session key dialog

- [x] 7.1 Fix usage display when local-only (no session key): if `is_estimated` is True, show `--/5h` and `--/7d` with empty progress bars instead of meaningless estimated percentages (local token counts can't be reliably converted to %). Keep token count in tooltip.
- [x] 7.2 Fix "Set Session Key..." dialog freeze: add `self.hide()` before `QInputDialog.getText()` and `self.show_window()` after, matching the pattern used by `open_settings()` and other handlers. The always-on-top timer (`_bring_to_front`) covers the modal dialog.
- [x] 7.3 Fix QMessageBox freeze after session key save (MessageBox appeared behind hidden window, blocking show_window). Removed unnecessary confirmation dialog.
- [x] 7.4 Run GUI tests and fix any failures
