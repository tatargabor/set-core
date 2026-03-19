## Why

The Stop hook's background transcript extraction silently dies every time due to a classic bash `set -e` + `(( count++ ))` bug. When `count=0`, `(( 0++ ))` returns the old value 0, which bash treats as false (exit code 1), and `set -e` kills the process. This creates a permanent failure loop: the staged migration file never gets deleted, so every subsequent Stop hook crashes at the same point, and the raw transcript filter never runs. No session insights are extracted.

## What Changes

- Fix 3 instances of `(( var++ ))` in `_stop_migrate_staged()` that crash under `set -e` when the variable is 0
- Audit the entire `wt-hook-memory` script for any other `(( ))` expressions vulnerable to `set -e`
- Clean up the stuck staged file in the reddit project

## Scope

- File: `bin/wt-hook-memory` (lines 1118, 1123, 1130)
- Side effect: reddit project's `.set-core/.staged-extract-*` stuck file cleanup

## Out of Scope

- Other `bin/` scripts (`set-project`, `wt-status`, etc.) — they don't use `set -e`
- The `$((expr))` assignment form is safe (never returns exit code)
- The "content required" errors in the log are from `set-memory rules add`, unrelated
