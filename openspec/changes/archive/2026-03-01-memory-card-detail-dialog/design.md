## Context

The `MemoryBrowseDialog` shows memory cards with content truncated to 200 characters. The `wt-memory get <id>` command returns the full memory record. There's currently no way to view full content in the GUI.

## Goals / Non-Goals

**Goals:**
- Click a memory card to open a detail dialog showing the full, untruncated content
- Show all memory fields: type, date, full content, tags, ID

**Non-Goals:**
- Editing memories from the detail dialog
- Delete action from the detail dialog
- Keyboard navigation between cards

## Decisions

**1. New `MemoryDetailDialog` class in the same file**
Add the dialog to `gui/dialogs/memory_dialog.py` alongside the existing classes. It's a simple read-only dialog — no need for a separate file.

**2. Click handler via `mousePressEvent` on the card QFrame**
The card is already a QFrame. Override or install an event filter isn't needed — instead, store the memory ID on the card and connect a click signal. Since QFrame doesn't have a `clicked` signal, use `setCursor(PointingHandCursor)` and install a `mousePressEvent` via a lightweight subclass or lambda on the card.

Simplest approach: subclass QFrame to `_ClickableCard` with a `clicked` signal, use that in `_create_memory_card`.

**3. Fetch full content via `wt-memory get <id>`**
Even though the card's `mem` dict may already contain the full content (in list/search mode), always call `wt-memory get` to guarantee completeness and consistency. The call takes <100ms.

## Risks / Trade-offs

- [Missing ID in summary mode] → The context summary endpoint may not include memory IDs. If `id` is missing from the `mem` dict, the detail dialog can show whatever content is available without the `get` call.
