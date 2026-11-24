## Why

The question-relay panel lists what waits on the channel only as one line: the agent, the kind, the
age and the decider's one-line verdict ("no decision — the sources do not settle it"). The operator
cannot see *what* is asked or *what* the system waits for without leaving the screen. When the same
kind of question comes again, there is no way to teach the system the answer once. The decider
abstains again tomorrow and the agent sits again. The owner asked for both on 2026-11-24, from a
screenshot of four questions waiting 29–52 minutes:

> *„kellene egy részletek gomb ami megmutatja mi a kérdés mire várunk, meg egy gomb ami megtanítja a
> rendszernek hogy ne várjon legközelebb és mi a válasz ilyenkor, egy kis magyarázattal fűzni is lehet
> hozzá pl "amikor ilyen commit van mindig engedélyt kapsz hogy commitolj az adott branchra" vagy "ha
> azt kérdezed kimehet-e a weboldal élesbe akkor ha a tervezet módosítás le van ellenőrizve akkor
> mehet""*

> *„ezeket projekt szinten kell gyűjteni és commitolni hogy [a teammate] is ugyanígy tudjon működni"*

Asked whether a taught rule may also approve an outward step (the second example is a production
step), the owner chose **„Mindig mehet"** (always). The rationale: a taught rule is the operator's
own answer, given in advance.

## What Changes

- Each waiting row on the question-relay panel gets a **Details** control. It opens an overlay showing
  the question text and options, the kind, how long it has waited, and what the decider did with it
  (proposal, tier, outcome, reason, checked references). For a call the decider never saw, it says so.
- Each single-question row that is not a permission prompt gets a **Teach** control. The operator
  writes the answer (pre-filled with the proposal or the agent's recommended option) and an optional
  short explanation or condition. Saving does three things:
  - appends a rule to the asking project's `.claude/rules/auto-answer-taught.md` in the project's
    main checkout;
  - commits that one file (pathspec-limited; no push);
  - answers the waiting call at once with the taught answer.
- The decider reads the project's taught rules **verbatim** in its prompt. A proposal backed by a
  checked quote from that file is tier `decided`, and **no outward-step exclusion applies to it**.
  A permission prompt stays excluded whatever a rule says.
- Because the file sits in `.claude/rules/`, every agent session in that project loads it, so
  agents stop asking what is already taught. A teammate's checkout gets the same rules through git.

## Capabilities

### New Capabilities
- `relay-teach`: the Details overlay and the Teach control on the question-relay panel, the
  project-level taught-rules file, and how a rule is written and committed.

### Modified Capabilities
- `fleet-auto-answer`: the outward-step exclusion gains one exception, an answer backed by a
  checked taught rule. The standing-delegation requirement gains the taught rules as a second
  verbatim source.

## Impact

- `lib/set_orch/fleet/auto_answer.py`: taught-rules loading, the prompt, and the exclusion exception.
- `lib/set_orch/fleet/auto_answer_worker.py`: carry the rule-backed flag to the exclusion; expose
  the full pending record for Details.
- New `lib/set_orch/fleet/relay_teach.py`: resolve the project's main checkout, append the rule,
  commit the one path, answer the call.
- `lib/set_orch/api/fleet.py`: `GET /api/fleet/question-relay/{call_id}/detail`,
  `POST /api/fleet/question-relay/{call_id}/teach`.
- `web/src/components/FleetRelay.tsx` and `web/src/lib/fleetRelay.ts`: two controls and two overlays.
- **Writes into another project's tree, on the operator's click:** one file under `.claude/rules/`
  and one commit containing only that path. Never a push. The project's own commit hooks run
  (leakscan included).
