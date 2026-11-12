---
name: feed-watch
description: Collect new items from the feeds this project declares in .set/feed-watch.yaml, through the user's own logged-in Chrome (slowly, read-only, no scraper), score them by the project's rubric, write the digest and draft replies for the ones above the threshold. Nothing is posted or sent; a human decides and sends. Use when the user asks to check the watched feed, collect leads, or produce the daily digest, or when the feed-watch pane's "Run now" fires.
---

# feed-watch: collect → score → drafts → digest

Everything specific to this project — which feed, what counts as an item, the rubric, the
threshold, the labels, the reply template, the copy gate — is in `.set/feed-watch.yaml`
and the files it names. **Read it first:** `set-feed-watch show` prints it resolved.

## Iron rules

- **Read only.** You never post, comment, react, like, share, join, follow, message or send
  anything, on any source. A human sends every reply.
- **Only the declared feeds.** Open only the `url` of a declared source and the permalinks of
  its items. No messenger, notifications, profiles, search, or other groups or pages.
- **Human pace, one tab.** Scroll a screen at a time, wait 2–4 seconds, read what is visible.
  No parallel requests, no scraper, no JavaScript bulk extraction.
- **On trouble, stop and report.** No refresh, no retry loop, no workaround for a login wall
  or a challenge.

## 0. Preparation

1. Ask the user to **bring the Chrome window to the front** (logged in to the source) and keep
   it there during the run. Measured: in a background window the feed rendered one item and
   then only loading placeholders.
2. `set-feed-watch show` — sources, caps (`max_items_per_run`, `max_age_days`), the item
   filter file, the rubric guidance file, labels, draft template and blocks.
3. `set-feed-watch seen` — the ids and text hashes already collected.
4. Load the Chrome tools in ONE ToolSearch call (see the `claude-in-chrome` skill), open **one**
   new tab on the source's `url`. Apply the source's `sort_hint`; if you cannot, say so in the
   report.

## 1. Collection

Scroll in small steps. Stop when ANY of these holds, and record which one:

- you reached the newest item already collected, or items older than `max_age_days`;
- you processed `max_items_per_run` items;
- **stall**: two consecutive scrolls brought no new item — only loading placeholders;
- **challenge**: a login wall, captcha, verification prompt, or an error page.

A run that collected zero items while the feed showed only placeholders is a **stall**, never
"no new items".

For each visible item:

1. Apply the project's item filter (`item_filter` file). Items it excludes are only counted.
2. Expand the full text. Get the permalink as the source's `permalink_hint` describes; if you
   cannot, write the link as unknown.
3. Dedupe: `printf '%s' "<text>" | set-feed-watch check-new --link "<permalink>"` → exit 3 means
   already collected: skip it and count it as a duplicate.
4. New item: write one file `<dir>/<YYYY-MM-DD>-<short-name>.md` (date = when it was posted, as
   far as the relative time allows; short name 2–5 ASCII words, hyphenated), using the
   project's `item_template` if declared. The item text goes **verbatim** — typos included —
   between the first two lines that are exactly `---`, and nothing else goes there (it is the
   dedupe hash's input). Do not record other people's names from comments.

## 2. Scoring

Score each new item by the rubric guidance file, using only facts readable from the item.
Append, in the item file, the machine line exactly as the declaration names it:

    <!-- <marker>:score <key>=<n> <key>=<n> ... -->

with every declared dimension, each within its `max`; then a human-readable table with a reason
per dimension, and a `- <reason label>: <one line>` line (it goes into the digest). Put risk
flags into that one line.

## 3. Drafts for items above the threshold

When the total meets `total_min` and every `dimension_min` is met, write
`<item-file-stem><drafts.suffix>.md` from the project's draft template. Every text meant to be
sent goes into a fenced block whose language is one of `drafts.blocks`, because the gate reads
exactly those. The draft says it is a draft that a human sends. Claim only what the template
allows; never invent a figure, client, deadline or price.

Then run `set-feed-watch gate <draft>` and fix the text until every line is PASS. Copy the
output into the draft. If it says **no gate configured**, say so in the report — the draft is
unchecked, not passed.

## 4. Digest

`set-feed-watch digest <YYYY-MM-DD>` → the declared digest file. Fix every WARNING (unscored
item, qualifying item without a draft) and run it again.

## 5. Report to the user

Keep the counts separate: **seen, new, duplicate, filtered**, and the **stop reason** (with an
exact description if it was a stall or a challenge). Then one line per item above the
threshold, and the digest's path. Commit only on request, and only the files written now
(pathspec-limited commit).
