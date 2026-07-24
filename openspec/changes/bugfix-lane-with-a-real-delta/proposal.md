## Why

A consumer declared a lane signal whose `lane` is `bugfix`, and **set-core's taxonomy has no
such lane**. Measured on `HEAD`:

```
UNIVERSAL_DEFAULTS keys → cleanup-after · cleanup-before · feature · foundational ·
                          infrastructure · schema
```

So a bug fix in that project cannot declare what it is. This is the fourth item of the
integration track and it is set-core's half: the project can describe its restoring lane, and
the framework has no slot to put it in.

Three further measurements decide the shape, and each is a defect the change must not repeat:

1. **`feature` and `foundational` are byte-identical** (`UNIVERSAL_DEFAULTS['feature'] ==
   UNIVERSAL_DEFAULTS['foundational']` → `True`). A taxonomy entry with zero behavioural
   delta already exists here, which is precisely the failure the 2026-07-19 verdict named:
   *"a taxonomy with near-zero behavioural delta is a false gate, and this repo already has
   three."* Adding a fifth name that changes nothing would make it four.

2. **The type list lives in at least three places, and two disagree.**
   `UNIVERSAL_DEFAULTS` holds six; `.claude/skills/set/decompose/SKILL.md:68` restates the
   same six as a hand-written enum string; `merger.py:2442` exempts
   `('infrastructure', 'config', 'docs')` — and **`config` and `docs` exist nowhere else**,
   so that guard's exemption list names two types nothing can produce. Its direction is
   benign today (it exempts nobody), which is exactly why it has survived: a stale second
   copy that costs nothing until someone reads it as the list.

3. **An unknown type is stricter, not looser.** `gate_profiles.py:181` warns and applies no
   per-type defaults, so every universal gate stays blocking. A consumer declaring `bugfix`
   today therefore runs the *most* conservative chain — which means this change must not
   accidentally be a loosening dressed as a taxonomy addition.

## What Changes

- A **`bugfix` lane** whose delta is real and points at the opposite end of the process from
  `feature`: a cheaper **entrance** (a fix restores conformance to a specification that
  already exists, so it does not carry a spec delta) paid for by a stricter **exit**.
- The **exit obligation** is what makes the lane different rather than merely cheaper: a
  change declared `bugfix` must produce evidence that the defect cannot return. set-core does
  not define what that evidence is — the project does, through the lane-signal mechanism that
  already exists and already delegates to a published answer.
- **One home for the type list.** The enum in the planning skill and the exemption list in
  the merger stop being independent copies.
- A **refusal to soften without the exit**: declaring `bugfix` in a project that publishes no
  exit evidence must not buy a cheaper chain. This is the change's central safety property and
  the reason it is not simply a seventh dictionary entry.

## Impact

- `lib/set_orch/gate_profiles.py` — the new lane, and the type list as a single source.
- `lib/set_orch/merger.py` — the stale exemption list.
- `.claude/skills/set/decompose/SKILL.md` — the restated enum.
- No change to `lane_signals.py`, `lane_evaluator.py` or `lane_gate.py`: the exit evidence
  rides on the mechanism shipped in `lane-contradiction-detection`, which is the point of
  having built it first.
- **Deployed to consumers** via `set-project init` (the skill file), so the enum change
  reaches projects.

## Open question — asked on the channel before building

Whether the cheaper entrance is conditional on the project declaring an exit signal, or
whether `bugfix` is simply refused in a project that declares none. Both are defensible and
they differ in the direction that matters: the first fails toward today's behaviour, the
second fails toward a loud stop. The consumer's own bug-fix lane is in daily use and blocking,
so their answer is evidence rather than opinion, and the goal states the two sides design
extensions together.
