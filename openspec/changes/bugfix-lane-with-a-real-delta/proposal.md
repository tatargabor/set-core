## Why

A consumer's restoring lane is in daily use and blocking; set-core has no lane that behaves
differently from any other. This is the fourth item of the integration track and it is
set-core's half — but **not in the shape this proposal first argued**, and the correction is
the useful part.

**What the first draft got wrong.** It opened a `UNIVERSAL_DEFAULTS['bugfix']` entry and
treated the taxonomy as the deliverable. The 2026-07-19 verdict's ordering constraint says the
opposite: build the differentiated pipeline **first, and alone**; a taxonomy comes only once
two provably different pipelines exist to choose between. Adding a name first is how *"the
router gets built and has nothing distinct to route to"*.

**What survives, and why the name is still in scope.** A lane entry is admissible when it
cannot exist without its delta. That is a structural property, not a promise — and it is what
the consumer's answer supplies (below): a `bugfix` declaration with no enforced exit obligation
is **refused**, so the entry is incapable of being an empty name.

Three measurements on `HEAD` set the bar, all of them defects already present:

1. `UNIVERSAL_DEFAULTS['feature'] == UNIVERSAL_DEFAULTS['foundational']` → `True`. A taxonomy
   entry with zero behavioural delta already exists — the verdict's named failure, in the tree.
2. The type list lives in three places and two disagree: the dictionary holds six, the
   planning skill restates the same six by hand, and `merger.py:2442` exempts
   `('infrastructure', 'config', 'docs')` where `config` and `docs` exist nowhere else.
3. An unknown type is **stricter**, not looser (`gate_profiles.py:181` applies no defaults, so
   every universal gate stays blocking). Anything this change does is a loosening relative to
   today, and it must buy that rather than spend it.

**The consumer's answer, with their measurements** (channel W#113), which decides the shape:

- **Refuse loudly, not fall back.** A `bugfix` declaration with no exit signal is an
  *incomplete declaration*, the same shape as a malformed delegation — and falling back to the
  feature chain would silently give something other than what the project stated. The project
  would believe it has a lane while running an ordinary one: a marker true of a narrower
  subject than its reader takes it for.
- **The discount's price is the evidence.** "A cheaper entrance paid for by a stricter exit" is
  only true if the exit is *enforced*. Their acceptance of framework silence elsewhere holds
  precisely because their own exit gate blocks; with no exit signal the sentence's second half
  is empty and the lane is just a discount.
- **The refusal binds the declaration, not the project.** A project declaring no `bugfix` lane
  keeps today's behaviour, which finding 3 shows is already the most conservative chain — so
  nobody loses protection by not asking for a discount.

## What Changes

- A **`bugfix` lane whose entry is conditional on an enforced exit obligation.** Declaring it
  without one is refused with a named error; the refusal is per declaration.
- The **exit obligation rides on the lane-signal mechanism already shipped** — the project
  declares what counts as evidence that the defect cannot return, and the framework delegates
  to the project's published answer. set-core defines the shape and holds no signal.
- **One home for the type list**, so the planning skill's enum and the merger's exemption list
  stop being independent copies.

## What This Deliberately Does NOT Change

- **No entrance gate on "is this fix restoring the spec or changing it?"** The consumer's rule
  asks exactly that question, and they reported — measured, not recalled — that **nothing
  enforces it**: of 536 `fix(...)` commits, 50 touch a specification or the knowledge store
  (**9.3%**), and they named an incident where a specification described automatic behaviour
  while the code was deliberately manual for two weeks and was never annotated. Their explicit
  caution was not to generalise the half they demonstrably do not keep. Adopting an unenforced
  rule as a framework gate would be inventing a mechanism, not reading theirs.
- **No router.** Not built, not designed, not stubbed.
- **No change to `lane_signals.py`, `lane_evaluator.py` or `lane_gate.py`.** The exit evidence
  rides on what `lane-contradiction-detection` shipped, which is why it was built first.

## Impact

- `lib/set_orch/gate_profiles.py` — the conditional lane, and the type list as one source.
- `lib/set_orch/merger.py` — the stale exemption list.
- `.claude/skills/set/decompose/SKILL.md` — the restated enum; deployed to consumers via
  `set-project init`.
