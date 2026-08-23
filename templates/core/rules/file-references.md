# File References — a path you show a human must be openable

When you name a file to the **user** — in a chat reply, a CLI message, a summary, a
status line — write it as an **absolute path**, optionally with a line number:

```
/home/user/code/project/.set/findings.json
/home/user/code/project/src/api/orders.ts:142
```

A relative path is not a path. It is a path *plus an unnamed base*, and the base is
your working directory, not the reader's. The reader's terminal resolves
`.set/findings.json` against wherever they happen to be — which in a worktree, a
subdirectory, or a second project is somewhere else entirely.

## The fail direction is the reason this is a rule

A relative path is never *wrong*. It is merely **unopenable**, and silently so:
click-to-open does nothing, `@`-completion finds no file, the editor jumps nowhere.
Nothing errors, nothing warns, and the reader is left to reconstruct the base by
hand — every single time. That is why "usually it works from the project root" is not
good enough: the cost lands on the reader, and it lands invisibly.

## Where relative paths still belong — this half is load-bearing

Do **not** absolutize these:

- **Code, and data written to disk.** A stored absolute path breaks the moment the
  tree is moved, cloned, or checked out as a worktree.
- **Commit messages, OpenSpec artifacts, specs, and anything else that gets
  committed.** An absolute path leaks the local username and directory layout into a
  public repository — see the release-safety rule. `/home/<user>/…` in a tracked file
  is a finding, not a convenience.
- **Anything a fingerprint, cache key, or identity is computed from.** Changing the
  string changes the identity, and comparisons across runs stop matching.

The split is: **store relative, display absolute.** The two are not in tension —
they are the same fact rendered for two different readers.

## Getting the base right

Do not guess the project root, and do not paste one from memory:

```bash
git -C <any-path-inside-the-repo> rev-parse --show-toplevel
```

If a tool handed you a relative path, resolve it against the root of the repository
**that tool was run in** — not against your own current directory, which may differ.
When you genuinely cannot determine the base, say so instead of printing a path that
looks openable and is not.
