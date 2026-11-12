---
name: set:blueprint
description: Pre-offer architecture blueprint — research the open questions with sourced verdicts, then write the architecture plan (where each part runs, how parts talk, data ownership, requirement→component map, sub-processors, hours vs price band, running costs, tests that gate the price), optionally a private visual page. Use when a client solution must be designed and checked BEFORE its offer is priced.
---

# set:blueprint — the architecture blueprint before the offer

The offer is priced from this document, not the other way round. The order is fixed:

1. **Research.** Answer the open questions with sourced verdicts.
2. **Blueprint.** Write the architecture plan.
3. **Hands-on tests.** The humans run the tests the blueprint lists.
4. **Review.** The team reviews the plan.
5. **Offer.** Only then is it written. The architecture appears in the offer as **2–4 lines**;
   the detail stays internal.

Outputs, in the consumer repository:

| File | Skeleton |
|---|---|
| `docs/research-<YYYY-MM-DD>.md` | [`templates/research.md`](templates/research.md) |
| `docs/architecture-plan.md` | [`templates/architecture-plan.md`](templates/architecture-plan.md) |
| A private visual page (optional, phase 3) | — |

## Phase 0 — Inputs, in this order

1. **Internal decisions**: the team's written decisions, test list and open questions.
   These win over every older source. If none exist, ask the requester for them before
   writing anything.
2. **Requirement list / previous offer**: the full list of what was promised or asked.
3. **Meeting notes, then transcripts**: for detail the notes dropped, such as wording,
   constraints and the client's own terms. Transcripts are evidence, not decisions.
4. **Open client questions**: anything still undecided becomes a ⚠ or an open question,
   never an assumption stated as fact.

Turn every test-list item and every open technical question into a numbered research
question (R1, R2, …).

**Client isolation:** a blueprint repository holds one client. Never copy another client's
material in, and never carry this client's content into a framework file or a memory.

## Phase 1 — Research (`docs/research-<date>.md`)

- **Run independent questions in parallel** (research subagents, a few questions each). Brief
  each subagent with:
  - the context;
  - the exact questions;
  - "official sources first, a URL for every claim, flag inferences, verdict per item".
- **Verdict scale, fixed:** **works** · **works with caveat** · **doesn't** · **unknown**.
  One verdict per question.
- **Mark every conclusion no source states** as *(inference)*.
- **Third-party figures** (prices, limits from blogs) are labelled as third-party.
- **Each item ends with the hands-on test** still to run, and what counts as passing.
- **Open with a summary table:** question · verdict · what it means for the design. Add a
  cross-cutting findings paragraph when one result changes several items (for example a
  data-residency gap).
- **Record the check date.** Plans, prices and product defaults change weekly, so re-check
  before the offer goes out.

## Phase 2 — Blueprint (`docs/architecture-plan.md`)

Fill every section of the template. A section that does not apply says so in one line; it
is not deleted. Sections and what makes each valid:

1. **The design in ~5 lines.** Someone reading only this knows where the system lives and
   why. Say which research result forced the main choice.
2. **Where things run.**
   - A Mermaid deployment diagram: devices, cloud services, SaaS, people.
   - A placement table: place · what runs there · whether it holds data.
3. **How the parts talk.** One row per link: from → to · protocol · auth / key · **where the
   key is stored** · **who can revoke it**. Then **account ownership**: every account is in
   the client's name, the provider of the work is a member, and there is a stated exit path.
4. **Data ownership.**
   - Which store holds what.
   - **One writer per table**, so sync never merges.
   - The minimisation applied to whatever leaves the most protected store.
   - Retention as a parameter.
   - Search approach. Keyword search is the default; semantic search needs a reason.
5. **Requirement → component mapping.** **Every** agreed requirement appears: with a
   component, or marked as a *proposed cut* or a *placeholder*. Keep the client's own
   domain words.
6. **Failure modes and monitoring.** What happens when each external dependency is down, a
   token dies, the host is silent; idempotency of outbound actions; backup and recovery
   time.
7. **Security and sub-processors.** Whenever personal or regulated data is processed, a
   table: sub-processor · role · region · legal basis. Correct any earlier promise the
   research disproved (for example "data stays in the EU").
8. **Effort estimate.**
   - Per component, **low and high hours**, grouped by module.
   - Totals in hours, days and money at the stated day-rate band.
   - Say plainly whether the low and high figures fit the price band.
   - **If they don't, list options and stop:** a cap with named cuts, phases, or a smaller
     scope, each with its effect on hours. **Never choose one, and never rewrite the plan
     around one.** That is the requester's decision.
9. **Monthly running costs.**
   - Who pays each line: the provider's fee vs the client's own subscriptions.
   - **Gross or net, and why** (the client's VAT status).
   - Currency rate stated as an assumption.
   - The real monthly total the client pays.
   - One-off extras listed separately.
10. **Tests that gate the price.** Test id · components it gates · pass criterion. Then the
    fallback for each failure, and its cost in hours.

**⚠ rule:** every statement that depends on something not yet tried is marked ⚠ and names
its test id (T1, T2, …). A ⚠ without a test id is a defect in the blueprint.

Prefer standard pieces over custom code — configuration, platform features, scripts, a
small database — and say where a custom part is unavoidable.

## Phase 3 — Visual page (optional, only when asked)

- Build it **from the committed research and plan**, never from new claims: every number on
  the page exists in those files.
- Follow the host's artifact rules: call the quickstart first, then load the design guidance.
- Typical content:
  - the five-line design;
  - a deployment diagram with vendor logos (Simple Icons) and generic icons for the rest;
  - a sequence diagram for the main flow;
  - the data-ownership diagram;
  - verdict badges for the research;
  - the hours and cost tables;
  - the ⚠ tests.
- The page is **private**. Internal content (hours, price band, internal risks) never goes
  on a page meant for the client. A client version is a separate, trimmed page.

## Handoff

- **Commit only the blueprint and research files**, by explicit path:
  `git commit -m … -- docs/research-<date>.md docs/architecture-plan.md`.
  Check `git diff --cached --name-only` first.
- **Report to the requester:**
  - the paths;
  - the **3–5 findings that change the price or the architecture**;
  - what is still untested.
- **Don't send summaries of the whole document.** The requester reads the document.

## Anti-patterns

- **Pricing before the blueprint**, or treating an earlier itemised price as anything but a
  placeholder.
- **A research verdict without a URL**, or an inference written as fact.
- **A requirement silently dropped** from the mapping.
- **Choosing the price option** on the requester's behalf.
- **Copying the client's data** (names, records, credentials) into the blueprint. The
  blueprint describes data classes, not data.
