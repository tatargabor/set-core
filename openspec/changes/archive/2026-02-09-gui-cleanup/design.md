## Context

The GUI was refactored from a monolithic `main_old.py` (4880 lines) into a modular mixin-based architecture under `gui/control_center/`. The old file and several transitional artifacts were left behind. Additionally, a `gui/platforms/` directory was superseded by `gui/platform/` but never deleted. Color profile definitions are missing keys that the code references, causing fallback to `#000000` (black).

## Goals / Non-Goals

**Goals:**
- Remove all dead code and unused files that remain from the refactor
- Fix color profile completeness so every `get_color()` call resolves to a proper themed value
- Eliminate confusing menu item duplication (Git > Push vs Worktree > Push Branch)
- Normalize emoji usage across menus (tray vs main vs context)

**Non-Goals:**
- Reworking the menu system to use MenuBuilder (if needed later, that's a separate change)
- Changing any runtime behavior or adding features
- Touching the `gui/platform/` stdlib shadow hack (works fine, just ugly)

## Decisions

**1. Delete `gui/main_old.py` entirely** — It's the pre-refactor monolith. No code imports it. Git history preserves it.

**2. Delete `gui/platforms/` (with 's')** — The active platform layer is `gui/platform/` (no 's'). The old directory has different API signatures and is completely unreferenced. Confirmed by grep: zero imports of `gui.platforms` anywhere.

**3. Delete `gui/widgets/` entirely** — The only widget (`ClickableLabel`) is unused by active code. If the directory had other widgets we'd keep it, but it's empty otherwise. The `__init__.py` only exports ClickableLabel.

**4. Delete `gui/control_center/mixins/menu_builder.py`** — Defines `MenuBuilder`, `MENU_ICONS`, and imports `set_tools.plugins.base.MenuItem`. None of this is used — menus are built manually. Remove the import from `__init__.py` if present (it's not currently imported there, confirmed).

**5. Add `text_secondary` to all 4 color profiles** — Used in `table.py:398` for "my machine" team rows. Values: light blue tones matching each theme. Also add `text_primary` to `high_contrast` (missing, causes `#000000` fallback on `#222222` background).

**6. Remove Worktree > Push Branch** — The Git > Push does `git push` (with auto upstream setup). Worktree > Push Branch runs `wt-push` script which does the same thing with extra project resolution. Since the context menu already knows the path, Git > Push is sufficient. Remove Push Branch and the `wt_push_branch` handler.

**7. Remove emojis from tray menu** — Main menu uses plain text ("Settings...", "Quit"). Tray menu uses emoji prefixed text ("+  New Worktree...", "⚙️  Settings...", "✕  Quit"). Normalize tray to match: plain text, no emojis.

## Risks / Trade-offs

- **[Low] Someone uses wt-push from GUI** → `wt-push` is still available as a CLI command, just not in the GUI menu. `Git > Push` covers the same use case.
- **[Low] ClickableLabel needed later** → Can be re-created trivially (18 lines). Git history has it.
- **[Low] MenuBuilder wanted later** → Same — easily recreated, or a fresh plugin system can be designed when actually needed.
