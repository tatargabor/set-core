# Projektpult — client questions and an issue board in one artifact

A private claude.ai Artifact page with two views:

- **Questions** (`#kerdesek`): the open questions collected for a client project. Each has up to
  three suggested answers (A, B, C) and a free-text answer. A saved answer shows its letter, who
  saved it and when; it can be changed or cleared. Filters: awaiting answer / answered here /
  all, by addressee group, and a search.
- **Issues** (`#issues`): a board with six columns side by side — TODO, In Progress, In Review,
  Blocked, On Hold, Done (3 columns per row below ~1100 px, one on a phone; never a horizontal
  scroll). A card opens an editor: title, status, area, owner, due date, description and the
  related question ids (a click jumps to the question). "New issue" mints the next `ISS-NN`.

Compared with a wave board (`templates/waveboard/`), this is for a client project's open
questions and loose work items, edited by people on the page; a wave board tracks one
multi-step job whose status is derived from evidence in the repository.

## Data — the artifact db

| path | written by | content |
|---|---|---|
| `catalog/questions` | Claude (seed) | `{project, subtitle, lang, groups, items[]}` — the question list |
| `answers/<question id>` | the page | `{q, choice: "A"\|"B"\|"C"\|"", text, by: <user id>, at: ISO time}` |
| `issues/<ISS-NN>` | seed, then the page | `{key, title, status, area, owner, note, refs[], due, order, created, updated, updatedBy}` |

Question statuses (`open`, `partial`, `conflict`, `answered`) describe the project's own
register; a question counts as done on the page when the register says `answered` or someone
saved an answer here. Issue statuses: `todo`, `inprogress`, `review`, `blocked`, `onhold`,
`done`. The UI language is `lang` (`hu` or `en`); every other label comes from the data.

## Making one

1. Write a spec (see `seed.py`'s docstring): project name, groups, questions with options,
   starting issues. Question ids must be ASCII (`U1`, not `Ü1`); put the display form in `label`.
2. `python3 seed.py spec.json <out-dir>` — validates and writes the documents.
3. Publish `page.html` with the Artifact tool: `capabilities: {"db": {}, "user": {"scopes": ["profile"]}}`,
   `icon: "checklist"`. Keep it private.
4. Seed: `ArtifactData set` collection `catalog`, doc `questions`, `file_path: <out>/catalog.json`;
   then `ArtifactData batch` with each `<out>/issues-batch-N.json` as `writes`.
5. Read back once (`ArtifactData list` on `issues`) and open the page.

To refresh the questions later, re-run the seed and `set` `catalog/questions` again with the
`if_version` you last saw. Answers and issues are not touched.

## Sharing

Everyone who can open the page reads everything on it. Writing needs Contributor or Editor
(set in the page's Share menu). Before sharing with the client, remove internal and private
questions from the spec (or keep a separate internal page) — the page has no per-question
visibility.
