---
name: regression-baseline
description: How to tell a real test regression from this repo's pre-existing failure debt — the set-diff against a baseline worktree, the three import roots and the session-end leak assertion that make the baseline an actual baseline, and why a stash inside a killable command must never be used. Use before claiming a test suite regressed or did not, and whenever comparing this working tree's failures against HEAD.
---

# Measuring a regression in this repo

> Moved out of `CLAUDE.md` on 2026-08-22 so it loads when a regression is actually being
> measured. Nothing was cut — the text below is that block verbatim.

**Known unrelated debt — and the figure is not the check.** Measured on a pristine checkout
of `HEAD` (2026-07-24, late): **81 failed / ~2980 passed / 21 errors**, and the failures are
not confined to `test_web_api_write.py` + `test_web_integration.py`. Pre-existing and outside
the current track.

**Do not quote this number as a baseline.** It has now been stale twice in one file: "17
failed" understated it by ~77, and "94 / 2631 / 21" — written earlier the same day — was off
by 352 passing tests within hours. The passing count also moves a few tests between runs. A
debt figure is a *measurement with a timestamp*, and a stale one waves a real regression
through as "expected".

**The check that works is a set diff against a baseline you actually ran.** Never a stash
inside a killable command — a timeout between the stash and the pop leaves a clean tree and
the whole session's work in `stash@{0}`, which looks exactly like a command that never
started:

```bash
git worktree add -q --detach /tmp/base HEAD
python -m pytest tests/unit -q -p no:randomly 2>&1 | grep -E "^(FAILED|ERROR) " | sed 's/ - .*//' | sort > /tmp/now.txt
# THREE import roots, and a session-end assertion that nothing leaked. Both matter — see below.
cat > /tmp/leakcheck.py <<'EOF'
import os, sys
def pytest_sessionfinish(session, exitstatus):
    base = os.environ["BASELINE_ROOT"]
    leaks = sorted({m.__name__ for m in list(sys.modules.values())
                    if getattr(m, "__file__", None) and "/set-core/" in str(m.__file__)
                    and not str(m.__file__).startswith(base)})
    if leaks:
        print(f"BASELINE LEAK ({len(leaks)}): " + ", ".join(leaks[:25]), file=sys.stderr)
        session.exitstatus = 99
EOF
(cd /tmp/base && BASELINE_ROOT=/tmp/base/ \
   PYTHONPATH=/tmp/base/lib:/tmp/base/modules/web:/tmp/base:/tmp \
   python -m pytest tests/unit -q -p no:randomly -p leakcheck 2>&1 \
    | grep -E "^(FAILED|ERROR) " | sed 's/ - .*//' | sort) > /tmp/base.txt
diff /tmp/base.txt /tmp/now.txt   # empty = no regression, whatever the counts say
git worktree remove /tmp/base --force
```

**The `PYTHONPATH` line and the assertion are not decoration — without them this check does
not compare two versions.** Measured 2026-07-24: `set-core` is installed editable, so its
`__editable___set_core_0_3_0_finder` resolves `set_orch` to `/home/…/set-core/lib` from
*anywhere*. A worktree at `/tmp/base` therefore ran the BASELINE TESTS against the WORKING
TREE's library — a hybrid, not a baseline.

Its fail direction is what makes it expensive: the usual change is additive, so old tests
still pass against new code and the failure sets come out identical. The check then reports
"no regression" having compared one version with itself, and it does so most convincingly
exactly when it is least earned. It only became visible when two baseline tests failed that
could not fail at `HEAD` — the hybrid's own tell, and it appeared by luck.

So: point `PYTHONPATH` at the worktree's source roots, and **assert where the imports came
from before believing the run**. This is the proxy-instead-of-the-thing class applied to a
version: `cd`-ing into a worktree is a proxy for running its code.

**And the first repair of it was itself incomplete, which is the more useful half.** It set
`PYTHONPATH=/tmp/base/lib` and asserted `set_orch` — one package, named by hand. Measured
afterwards, prompted by an integration peer generalising the finding on their own side: this
repo puts first-party code under **three** roots, and a raw `.pth` entry hard-codes
`modules/web` to the development tree. `set_project_web` is imported by 10+ unit test files
and was still coming from the working tree, so the "corrected" baseline was *still* partly
hybrid. The named list was a second copy, and it drifted at the moment it was written.

Hence the session-end check above, which asserts **the thing** — no module loaded from any
set-core checkout other than this one — instead of a list of paths somebody has to maintain.
Measured on `HEAD` with full isolation: **0 leaks, 106 failure entries, identical to the
partially-isolated run**, so the earlier conclusion survives while the evidence for it is now
real.

**One thing this does NOT cover**, raised by the same peer with their own measurement: a
**generated artefact** can come from the other tree even when every source path is right,
because it is a product, not a source (their case: a generated database client resolved from
the main tree's `node_modules`, so worktree source ran against main-tree schema — the same
hybrid, and additive changes keep it green). Measured here: set-core's Python has **no
generated layer** (`find lib modules set_tools -name '*_pb2.py' -o -name '*_generated*.py'`
→ empty), so `tests/unit` is not exposed. The dashboard under `web/` does have a build
product, and that path has **not** been measured — do not assume it is clean.
