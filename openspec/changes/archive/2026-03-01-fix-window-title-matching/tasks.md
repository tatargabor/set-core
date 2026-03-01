## 1. Shared matching utility

- [ ] 1.1 Add `title_matches(search, window_title) -> bool` to `gui/platform/base.py` — exact match OR starts with `search + " — "` (em-dash) OR starts with `search + " - "` (hyphen)

## 2. macOS platform fix

- [ ] 2.1 Update `find_window_by_title()` in `gui/platform/macos.py` — replace AppleScript `contains` with boundary-aware matching (exact, `starts with "$title — "`, `starts with "$title - "`) in both the app_name and no-app_name code paths

## 3. Linux platform fix

- [ ] 3.1 Update `find_window_by_title()` in `gui/platform/linux.py` — use `title_matches()` in both the primary WM_CLASS path (currently only checks em-dash, missing hyphen) and the fallback xdotool path (currently returns first substring match without post-filtering)

## 4. wt-status bash fix

- [ ] 4.1 Add `match_window_title()` bash helper in `bin/wt-status` — checks 4th field of cache line for exact match or separator-prefixed match (` — ` or ` - `)
- [ ] 4.2 Update `is_editor_open()` macOS path — replace `grep -F "$wt_basename"` with `match_window_title` helper on cached window data
- [ ] 4.3 Update `is_editor_open()` Linux path — post-filter xdotool results with the same boundary logic (xdotool `--name` is substring, verify with `getwindowname` + helper)

## 5. Tests

- [ ] 5.1 Add GUI test for boundary-aware title matching (test `title_matches` utility and verify double-click doesn't focus wrong window when repo name is prefix of worktree name)
