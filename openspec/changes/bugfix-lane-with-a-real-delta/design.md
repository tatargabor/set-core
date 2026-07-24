## Context

Two things arrived within three minutes of each other and they decide this design together.

A goal-alignment re-read of the living record found this change's first draft on the wrong
footing: it opened a `UNIVERSAL_DEFAULTS` entry, and the 2026-07-19 verdict's ordering
constraint forbids exactly that — *build the differentiated pipeline first, and alone; the
taxonomy comes only once two provably different pipelines exist to choose between.* The
record also carries the consumer's own measurement that **work type is not the axis that
varies in practice**: chore, bug, feature and hotfix differ by label and by whether a manual
post-deploy step exists, not by path.

The consumer then answered the question the draft had asked, and their answer is what makes a
lane entry admissible at all: **refuse a `bugfix` declaration that carries no enforced exit
obligation.** Under that rule the entry *cannot* be an empty name, which satisfies the
ordering constraint rather than evading it.

Measured on `HEAD`, and each of these is a defect already in the tree:

- `UNIVERSAL_DEFAULTS['feature'] == UNIVERSAL_DEFAULTS['foundational']` → `True`.
- The type list lives in three places; `merger.py:2442` exempts `config` and `docs`, which
  exist nowhere else.
- An unknown `change_type` applies no defaults (`gate_profiles.py:181`), so every universal
  gate stays blocking — today's `bugfix` runs the *strictest* chain, not a lenient one.

## Goals / Non-Goals

**Goals:**

- One lane whose behavioural delta is real, enforced, and impossible to obtain without paying
  for it.
- Keep every definition of "sufficient evidence" on the project's side.
- Leave a project that declares nothing exactly where it is today.
- Give the other three taxonomy entries a yardstick they currently lack.

**Non-Goals:**

- **The router.** Not built, not designed, not stubbed.
- **An entrance gate on "does this fix restore the specification or change it?"** — see D4.
- Any change to `lane_signals.py`, `lane_evaluator.py` or `lane_gate.py`.
- Proving a change's lane is correct. This machinery can only prove a contradiction.

## Decisions

**D1 — The lane entry is conditional, and the condition is structural rather than a promise.**
`bugfix` resolves to a cheaper entrance **only** when the change's project declares an enforced
exit obligation. Otherwise the declaration is refused with a named error.

Rejected: falling back to the `feature` chain. The consumer's argument is the one that decides
it, and it is not about danger — the feature chain is stricter, so nothing breaks. It is about
**belief**: the project declared a lane, believes it has one, and silently runs an ordinary
change. That is the marker-true-of-a-narrower-subject class, and a false belief is what carries
a wrong decision later. It is also the same shape as `_parse_answer` refusing a malformed
delegation: silence would fall back to something other than what was declared.

**D2 — The refusal binds the declaration, not the project.** A project that declares no
`bugfix` lane keeps today's behaviour. Since an unknown type already yields the most
conservative chain, nobody loses protection by not asking for a discount — so the refusal
cannot be experienced as the framework getting stricter.

**D3 — The project maps its vocabulary onto set-core's change types, because only the project
holds both halves.** A project declares, once, which of its lane signals enforce a given
change type. The framework reads that mapping and holds none of it.

Two alternatives were rejected, and the second is the one worth recording:

- *A new per-signal field naming the change type it gates.* Rejected: it puts the mapping in N
  places, and the mapping is one fact.
- *Comparing `LaneSignal.lane` to `change_type` directly.* Rejected, and it was rejected once
  already inside `lane_signals.py` for the reason that still holds: **the mapping between a
  project's lane vocabulary and set-core's change types is domain.** A project whose lanes are
  called `restoring` and `changing` would have to rename them to set-core's words, which is
  the design that has failed rather than the project. Comparing the two strings looks like the
  obvious implementation precisely because the two vocabularies happen to overlap in one
  consumer — the worst reason to build a coupling.

**D4 — No entrance gate on the conformance question, and the reason is a measurement rather
than scope discipline.** The consumer's rule asks a single question at the start of a fix:
*does this restore what the specification already says, or change what the system should do?*
It is the natural thing to generalise, and their measurement is why it is not:

```
fix(...) commits            536
touching spec or knowledge   50   →  9.3%
```

plus a named incident — a specification describing automatic behaviour while the code was
deliberately manual for two weeks, never annotated — and the fact that the gate intended to
enforce it does not exist in their tree either. They asked explicitly that the half they
demonstrably do not keep not be generalised.

The general principle, which is why this belongs in a design document and not a scope note:
**a framework gate that enforces what the most advanced available practice cannot keep does
not protect anyone — it gets switched off, and takes the warning with it.** The 9.3% does not
mean they lack entrance discipline; two other gates of theirs block or warn. It means *that
particular question has no gate*, by their own account.

**D5 — "Enforced" means the signal blocks, not that it exists.** An exit obligation satisfied
by a WARN-severity signal would leave the discount unpaid: the entrance gets cheaper and
nothing stops the defect returning. Lane signals already start at WARN and reach ENFORCE only
when the project's own declared measurement is recorded, so this reuses a mechanism that
already refuses unproven promotions rather than adding a second notion of strictness.

The consequence is deliberate and should not be softened later: **a project cannot obtain the
bugfix discount on day one.** It must first run its exit signal at WARN, record the measurement
its own promotion condition names, and only then does the cheaper entrance become available.
That ordering is the whole point — the evidence is the price.

## Risks / Trade-offs

- **A conditional lane is harder to explain than a dictionary entry** → accepted. The
  alternative is the fourth zero-delta entry, and the tree already shows what those become:
  `feature` and `foundational` are byte-identical and nobody noticed until it was measured.
- **The mapping is a new declaration surface** → kept to one file and one shape, and it is the
  only place a project's vocabulary meets set-core's. A near-miss key in it is refused the same
  way the lane-signal reader refuses one, so a typo cannot silently mean "no mapping".
- **A project could declare a trivial exit signal to buy the discount** → true, and out of
  scope for a mechanism: the signal must still reach ENFORCE through its own recorded
  measurement, and a project willing to fake that can already fake anything else. What the
  design refuses is obtaining the discount *by omission*, which is the case that happens by
  accident.
- **The living record says work type is not the axis that varies** → this change does not
  claim otherwise. It adds one lane because a consumer's restoring lane exists and blocks, and
  it makes the entry incapable of being empty. It does not add three more, and it does not
  route between them.

## Open Questions

None blocking. One will be asked on the channel when the exit obligation's shape is specified:
what the consumer's own gate treats as *sufficient* evidence — a stable identifier anywhere in
a test, within a directory, or inside an assertion. That is shape rather than value, so it is
the framework's to define; but the only evidence available for defining it well is theirs.
