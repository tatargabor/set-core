## Context

`set-project init` deploys everything under `.claude/skills/set/` and `.claude/commands/set/`
through the provenance-guarded tree copy in `lib/project/deploy.sh` (`_deploy_skills`,
`_deploy_commands`). A file absent from the consumer is deployed as new; a file the
consumer changed is left alone; a file the consumer deleted is tombstoned. Adding a new
directory under `.claude/skills/set/` therefore needs no registry entry and no deploy code.

The method this skill encodes was first run by hand in a consumer project: a research
document answering an internal test list item by item, then an architecture plan that
mapped every agreed requirement to a component, and a private visual page for the team.
That consumer's documents are the worked example of the output shape; none of their
content is copied into the framework.

## Goals / Non-Goals

**Goals:**
- One repeatable shape for the pre-offer blueprint across projects.
- Every claim in the research carries a source or is marked as an inference.
- Every untested assumption in the blueprint is visible and tied to a test that gates the price.
- The price check presents options; the humans choose.

**Non-Goals:**
- Writing the offer itself. The offer is written after the blueprint and the tests, by
  the people who own the client relationship; the architecture appears there in a few lines.
- Turning meetings into requirements automatically. The framework permanently excludes that
  pipeline. This skill starts from decisions and requirement lists that humans already wrote,
  and is invoked on request.
- Any deployment or infrastructure action. The blueprint describes; it never provisions.

## Decisions

- **A skill with templates, not code.** The work is judgement-heavy and the inputs are
  documents; a CLI would add nothing a checklist does not. Alternative considered: a
  `set-blueprint` command that scaffolds the two files — rejected, the skeletons are two
  copies and the agent already writes files.
- **Templates live inside the skill directory.** They then deploy with the skill through
  the same tree, and a consumer that customises them keeps its version (provenance rule).
- **The verdict scale is fixed** — works / works with caveat / doesn't / unknown — so
  research documents from different projects read the same way and summary tables can be
  compared.
- **The price check never picks.** When the estimate does not fit the band, the skill lists
  concrete options (a cap with named cuts, or phases) and stops. In the first run, the
  requester explicitly deferred that choice; a skill that chose would have had to be undone.
- **Account ownership in the client's name** is a required section, because every later
  exit, revocation and handover depends on it.

- **Settled by the user (2026-10-27):**
  - Reading meeting notes is acceptable: the skill starts from decisions people already
    wrote down and runs only on request, so it is not the excluded meeting→requirements pipeline.
  - The name stays `set:blueprint`, as `set:kb` does.
  - The default input stays the newest `docs/*decisions*.md`, overridable by an argument.

## Risks / Trade-offs

- [The skill reads like a checklist and an agent fills sections with filler] → each
  required section names what makes it valid (e.g. every row of the communication table
  names who can revoke the key), and the unit test checks the sections exist, not their prose.
- [Research ages quickly — product plans and limits change week to week] → every research
  document carries its check date, and the skill tells the agent to re-check before an
  offer goes out.
- [Client content leaking into the framework through the templates] → templates contain
  placeholders only; the worked example is referenced by shape, never quoted.
