## 1. CLI and job file

- [x] 1.1 Stop writing item `by`; drop legacy `by` in `save_job` and `content_of` [REQ: items-carry-an-assignee-chosen-from-the-boards-list]
- [x] 1.2 `assignees` list and item `assignee` in the payload; `init --assignees`, `assignees`, `add --assignee`, `assign` [REQ: items-carry-an-assignee-chosen-from-the-boards-list]
- [x] 1.3 Unit tests: assign/clear, unknown item, no `by` after sync [REQ: items-carry-an-assignee-chosen-from-the-boards-list]

## 2. Page and skill

- [x] 2.1 Page: no machine on rows or the sync line; per-item assignee select; `board/assignees` subscription and write [REQ: the-board-page-is-read-only-and-works-offline]
- [x] 2.2 Skill: assignees in the structure, reading `board/assignees` back, `assign` [REQ: items-carry-an-assignee-chosen-from-the-boards-list]
