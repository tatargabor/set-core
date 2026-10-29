## 1. CLI

- [x] 1.1 `wait --options`, `answer`, `import --dir`, `lang`; `lang` in the payload only when set [REQ: page-choices-come-back-through-import]
- [x] 1.2 Unit tests: options + answer, import applies newer only and is idempotent, lang [REQ: page-choices-come-back-through-import]

## 2. Page

- [x] 2.1 Status select over the pill, `board/statuses`, newer-than-updated overlay, "set on the page" [REQ: viewers-set-statuses-and-answer-waits-on-the-page]
- [x] 2.2 Answer buttons + "Other" field, `board/answers`, answered state with "change", focus kept across live re-renders [REQ: viewers-set-statuses-and-answer-waits-on-the-page]
- [x] 2.3 Hungarian labels from `lang` [REQ: the-page-speaks-the-boards-language]
- [x] 2.4 Browser check with a mock db: option click, other-text submit, status pick land in their documents; 0 overflowing controls at 1280 and 375 [REQ: viewers-set-statuses-and-answer-waits-on-the-page]
- [x] 2.5 Skill: reading back with ArtifactData + import, acting on answers [REQ: page-choices-come-back-through-import]
