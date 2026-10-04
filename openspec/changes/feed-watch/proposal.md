## Why

A consumer project hand-built a working watcher for a public Facebook group: it reads new posts
through the user's own logged-in Chrome, keeps one Markdown file per post, scores each post
against a rubric, and prepares reply drafts that a human sends. Nothing about the mechanism is
specific to that consumer. The rubric, the offer it scores against, the voice of the drafts and
the person who sends them are. The user wants the mechanism in set-core so that other projects
can reuse it, with the domain staying on the project's side.

The first version exists and is in daily use, so this change lifts it rather than redesigning
it. It generalises the shape and keeps the consumer's foundation working: a project that adopts
the module keeps its file layout, its language and its rubric.

## What Changes

- **New module `feed-watch`**: a skill, a CLI (`set-feed-watch`) and an opt-in Claude Code pane,
  all generic. A project turns it on with a declaration file. Nothing runs without one.
- **Collection** through Claude in Chrome in the user's own logged-in browser. It is slow and
  read-only, one tab, with the window in front. It has a per-run item cap, and on a stall, login
  wall, captcha or error page it stops and reports. It never retries in a loop. The first source
  adapter is a Facebook group feed, and the adapter boundary is there so a second source does not
  reshape the module.
- **Storage**: one Markdown file per item, verbatim text between fixed markers, and dedupe by the
  source's item id with a normalised text hash as the fallback.
- **Scoring against a project-declared rubric.** The project declares the dimensions, scales,
  labels, guidance file and threshold, for example "total ≥ N and dimension X ≥ M". set-core ships
  no rubric and no default offer. It reads a machine score marker whose name the project can set,
  so the consumer's existing files parse unchanged.
- **Daily digest** generated from the item files, ranked by score, with warnings for unscored
  items and missing drafts.
- **Reply drafts** for items above the threshold, in fenced blocks a gate can read. The project
  declares a copy-gate command, and the module runs it and records its output in the draft.
  **A human sends. The module never posts, comments, reacts or sends anything.**
- **Scheduled pane**: a Claude Code plugin pane at times the user chooses, with the actions
  "Run now", "snooze 1 h", "tomorrow" and "off". The opt-in lives outside every repository in
  `~/.config/set-core/` and is keyed to the Claude account that made it, so the pane stays silent
  for any other account. Two open sessions do not both ask.
- Not breaking: this is new and opt-in.

## Capabilities

### New Capabilities
- `feed-watch-collection`: read-only collection of feed items through the user's browser, the
  stop conditions, the per-item file format and dedupe, and the source-adapter boundary.
- `feed-watch-scoring`: the project-declared rubric and threshold, score parsing, the digest,
  the reply-draft format, and the copy-gate hook.
- `feed-watch-schedule`: the per-account opt-in, the scheduled pane and its four actions, and
  the single-asker lease across sessions.

### Modified Capabilities
<!-- none -->

## Impact

- New: `lib/set_feedwatch/` (Python package, domain-free), `bin/set-feed-watch`, a deployable
  skill and plugin template, and unit tests for both the Python and the plugin logic.
- Deploy: `set-project init` installs the skill and plugin only for a project that opts in. A
  project that does not opt in gets no new file.
- Local state outside every repository: `~/.config/set-core/feed-watch.json` (opt-in) and
  `feed-watch.state.json` (slot state).
- No new runtime dependency on the Python side. The pane uses the existing Claude Code plugin API.
- Confidentiality: set-core persists nothing derived from collected items. Item files, digests
  and drafts live only in the consumer's tree.
