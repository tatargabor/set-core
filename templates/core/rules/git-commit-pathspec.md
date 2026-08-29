# Git commit — name the files, every time

`git commit` commits the **whole index**, not what you added. If another session staged
something while you were working, it goes into *your* commit, under *your* message — and
their message is gone. So the commit always carries a pathspec:

```bash
git commit -q -F - -- <path> [<path>…] <<'MSG'      # the pathspec goes BEFORE the heredoc
…message…
MSG
```

**The reflex is not "remember to add it". It is: a `git commit` line without `--` is not
finished** — whichever message form you use (`-m`, `-F file`, `-F -`).

## Why this is a rule and not advice

Measured five times, in two different repositories, *after* the correct form was already
written down:

| when | what went in | what was lost |
|---|---|---|
| `06c1cc69` | 11 foreign files (1844 lines) | another lane's commit message: a schema decision |
| `9a635b27c` | 19 files, **16 foreign** | **two** sessions' commit messages |
| `839b32b83` | 8 files, **7 foreign** | five user decisions with their measurements |
| `274417f40` | 9 files, 4 foreign | another lane's measurement of four extractor gaps |
| 2026-08-29 | 1 file — **by luck** | nothing; the index happened to be empty |

Every one of those had a **disciplined `git add`**. That is the trap: your own command looks
correct, and the damage arrives from someone else's index. The fifth case is the instructive
one — it went right, and only because nobody else had staged anything in that second.

⚠ **The content is not what is lost — the commit MESSAGE is.** The files survive in the tree
and the specs still validate. What disappears is the reasoning: why a decision was made, what
was measured, which question is still open. And rewriting history in a shared branch with
live sessions costs more than the damage, so **the fix is prevention; afterwards, leave it**.

## When a pathspec is not enough

`git commit -- <path>` commits that path's **working-tree** content and ignores the index.
So if one file holds *your* change **and** a foreign uncommitted change, the pathspec still
takes both. Measured: a carefully `git apply --cached`-staged file still carried a third,
foreign hunk (34 lines) into the commit.

```bash
git diff <file> > /tmp/f.patch          # split the hunks; find which are yours
git apply -R /tmp/foreign.patch         # take the foreign one out, temporarily
git commit -q -F - -- <file> <<'MSG'    # now the working tree holds only yours
git apply /tmp/foreign.patch            # put it back exactly as you found it
```

## Check before, not after

```bash
git status --short           # what is in the tree
git diff --cached --name-only   # what is in the INDEX — this is what an unqualified commit takes
```

`git add -A` and `git add .` are never correct in a tree that other sessions share.

## Enforcement

Prose did not hold — four of the five cases happened *after* this was written down. A
`PreToolUse` hook on `Bash` that asks for confirmation on an unqualified `git commit`, and
prints the staged file list so a foreign entry is visible, is what actually stopped the fifth.
If your project has no such hook, treat the pathspec as part of the command, not as a habit.
