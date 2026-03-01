## 1. Clickable Card

- [ ] 1.1 Create `_ClickableCard(QFrame)` subclass with a `clicked` signal and `PointingHandCursor`
- [ ] 1.2 Replace `QFrame()` with `_ClickableCard()` in `_create_memory_card`, store memory dict on card

## 2. Detail Dialog

- [ ] 2.1 Create `MemoryDetailDialog` class — fetches full content via `wt-memory get <id>`, displays type badge, date, full content (selectable, word-wrapped), tags, and ID
- [ ] 2.2 Handle fallback: if no `id` in memory dict, show available content without `get` call
- [ ] 2.3 Set `WindowStaysOnTopHint`, add Close button

## 3. Wiring

- [ ] 3.1 Connect `_ClickableCard.clicked` to open `MemoryDetailDialog` in `MemoryBrowseDialog`

## 4. Tests

- [ ] 4.1 Add GUI test in `tests/gui/test_XX_memory_detail.py` covering: card click opens detail dialog, detail dialog shows full content, fallback without ID
