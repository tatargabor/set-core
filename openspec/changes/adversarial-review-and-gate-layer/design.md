# Design — adversarial review and the first gate layer

This design is mostly **adoption, not invention**. A consumer project has run this mechanism daily
for weeks; what follows records what was taken, what was deliberately left behind, and the places
where their implementation's own measured failures decide the design here.

---

## 1. The word "gate" is already taken, and conflating the two would be expensive

| | engine integration gates | this layer |
|---|---|---|
| runs at | merge time, inside orchestration | push time, in this repository |
| subject | a consumer project's build/test/e2e | this repository's own artifacts and source |
| owner | `lib/set_orch/` (runtime) | `scripts/gates/` (development-time) |
| failure means | that merge does not land | that push does not leave |

They share a name and nothing else. Every new file, log prefix and test in this change says **push
gate** where ambiguity is possible, and nothing in `lib/set_orch/` is touched — which is also the
architectural check: a development-time gate that needed to reach into the runtime would be a sign
it belongs somewhere else.

---

## 2. Two review branches, because one reviewer finds one class

The adopted mechanism runs **two independent agents in parallel**, not one "please review this":

- **against the code** — assumes the plan is wrong and tries to prove it from the source, with
  `file:line` evidence for every claim, working through a named list of attack points rather than
  "having a look";
- **against the rules** — checks the plan item by item against the project's mandatory rules, and
  produces a *gap list*, not an opinion.

The split is not stylistic. In the measurement that produced the rule, the code branch found a
deleted route that another feature depended on and a replacement mechanism that serialised where the
original deduplicated; the rules branch is what catches a missing traceability tag, an unregistered
scheduled job, a `MODIFIED` requirement written as `ADDED`. Neither branch finds the other's class,
and a single reviewer told to do both does the easier one.

**Both branches are told two things that look like politeness and are not.** That a finding must
come with a failure scenario — concrete input → wrong output — because a finding without one cannot
be argued with or dismissed. And that **inventing a finding is worse than an empty list**: an agent
asked to be adversarial and finding nothing will manufacture something to look useful, and the cost
of a false finding is a real plan change.

**And a mandatory closing section: what was checked and found correct.** Without it, "no findings"
and "did not look there" produce identical output. This is the same rule this repository already
states for gaps — a gap is not a zero — applied to a review.

---

## 3. What decides whether the review happened: the artifact, not the report

The gate does not ask an agent whether it reviewed. It measures a **trace**: a `review-findings.md`
in the change directory, containing at least one severity marker or an explicit statement of no
findings. This repository has already measured why: an agent asked to create a file reported `Done.`
with exit 0 while the tool layer had refused the write, and the file did not exist. A gate that waits
on an action measures the action's trace, never the report.

**The stub check is part of the trace, not an extra.** A touched empty file satisfies "the file
exists" and satisfies nothing else.

---

## 4. Their gate's own fail-open defect decides how ours matches

The consumer's implementation carries a documented correction that is worth more than the gate:

> It matched only `^\|.*CRITICAL.*OPEN` — a **status-table row**. Measured: 3 of 17 findings files
> contain no table at all. A change whose own header read "apply is BLOCKED — one critical finding
> open" passed the gate, and was archived with three unresolved decisions.

That is this repository's own defect class — *the check verifies the shape and is silent about the
content* — in someone else's file. Three consequences, adopted verbatim:

- **Match several overlapping shapes**, not one: a table row, a status line, a heading ending in the
  status, a list item ending in it. The finding decides its own form; the gate must not.
- **Strip fenced blocks before matching.** An example inside a code block is not data. The same class
  already bit this repository's OpenSpec delta parser, which ends a section at any `##` — including
  one inside a fence.
- **A prose signal warns, it does not block.** Their gate reads the file's own claim that apply is
  blocked as a *warning*, because 4 of 7 such hits were rule quotations or back-references, and the
  negated form ("apply is NOT blocked") means the opposite. A blocking check built on prose fires on
  quotations; a gate that fires on nothing gets skipped.

**Promotion from warn to block is earned by measurement**, on their rule and ours: at least half the
signals real, over two consecutive weeks. A warning that is right half the time is a candidate; one
that is right a tenth of the time is noise with a future.

---

## 5. Baselines, and why the layer cannot be switched on without them

Measured here: **24 changes have started work and none has a review artifact**; **404 exception
handlers do nothing but `pass`**. A gate introduced against those numbers blocks the next push, and
what happens next is not that 404 handlers get fixed — it is that the skip variable goes into a
shell profile and the gate is off forever.

So every gate that meets existing debt ships with a baseline seeded from the measured current state,
and:

- **the baseline may only shrink**, enforced by the gate itself against the committed previous
  version — not by asking. A baseline that can grow is a gate that can be disabled one line at a
  time, silently, by the person the gate exists to stop;
- **removing a line is the unit of progress** and needs no ceremony;
- **growing it is possible but must be deliberate** — an explicit environment variable, whose use is
  visible in the commit.

One correction adopted from their implementation, because it is the kind that only appears in use:
their baseline stores a change's bare name, while archiving prefixes the directory with a date. A
strict match therefore turned four baselined changes into blocking failures **at the moment they were
archived**. Match both forms.

---

## 6. The gate on the gates

Every gate ships with a self-test that runs it **twice**: once against a fixture that violates the
rule (it must fail) and once against a clean fixture (it must pass). A gate with no self-test is
itself a failure of the meta-gate.

This is the strongest single thing to adopt, and it is the direct application of a rule this
repository already has: a test that fails in neither direction measures nothing, and a mutation whose
restore is never asserted leaves the tree broken while the run goes green. The two-directional
self-test is that discipline made mandatory instead of remembered.

The fixtures live in a throwaway directory, never in this repository's own tree — a gate under test
must not be measuring the repository that contains its own fixtures. That is the
measurement-inside-the-corpus class, and it has already cost this repository four wrong readings in
one day.

---

## 7. What is deliberately NOT adopted

The consumer runs ~50 gates. Most are theirs and must stay theirs:

| their gate class | why not here |
|---|---|
| pricing, payment matching, document numbering, ticketing sync | domain. The framework must not learn a business |
| schema migration, ORM delete safety, seed conventions | a specific persistence stack; belongs to a project type, not to Layer 1 |
| endpoint auth, UI entry points, e2e test ids, design tokens, silent pagination | web-shaped. These are **good candidates for `modules/web/`** later — a plugin may carry them without the core knowing |
| production build, deploy parity | this repository has no such build or deploy |

The rule underneath: a gate belongs in this layer only if it enforces a rule the framework itself
already states, and can be checked without knowing what kind of project it is looking at. Everything
adopted below passes that test; everything above fails it.

**And the deployment half is a separate change on purpose.** A consumer that already runs a chain
must not receive a second one — the framework's standing rule is that a proven foundation is
extended, never replaced. Shipping these gates as templates would put a second, weaker chain into
projects that already have a stronger one, which is the failure that rule exists to prevent.

---

## 8. Which existing rules get a gate first, and why those

Chosen by measurement rather than importance, because an unenforced rule with zero violations proves
nothing and a gate that fires daily on nothing gets skipped:

| gate | measured today | fail direction |
|---|---|---|
| silent exception swallowing | 404 handlers in 83 files, 0 bare `except:` | baseline-heavy; blocks only new ones |
| `openspec validate --strict` on touched changes | 14 of 36 active changes fail | blocks the change you touched, not the other 13 |
| completed change left unarchived | last archive 2026-07-31 | warn first — "completed" is a judgement |
| rule corpus truthfulness | 14 of 46 cited paths do not exist | blocks a rule that cites nothing |

**Only touched changes are validated, deliberately.** A gate that demands all 36 be fixed before any
push is a gate nobody can pass; one that demands the change you are working on be clean is a gate
that is always passable and monotonically improves the number.

---

## 9. What this design does not know

- **Whether pre-push latency is acceptable here.** The gates are cheap individually, but nobody has
  measured the whole chain on this repository. If it is slow, scope by what the push touches — the
  consumer already does exactly that, and the mechanism is adoptable if needed.
- **Whether the 404 handlers are actually 404 problems.** The count is exact (AST, not grep) but
  unclassified: some are legitimate. The baseline makes the classification optional rather than a
  precondition, which is the point of a baseline.
- **What the review costs on a change of this repository's size.** Theirs measured ~330k tokens for
  the two branches on a large change, and judged it far cheaper than implementing a plan that drops a
  feature. That trade is theirs, on their change sizes; it is quoted here as their measurement, not
  claimed as ours.
