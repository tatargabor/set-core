## 1. The unit becomes a fact (precondition for a non-destructive rename)

- [ ] 1.1 Find every caller that re-derives a unit from a label (`scopes.unit_name(...)`, `_as_scope(label)` on a label rather than a unit) and list them in the change before touching any — the count is the measurement, and a missed one fails as "no such unit", which reads as the agent being gone [REQ: the-scope-unit-is-a-stored-fact-not-a-name-derived-from-the-label]
- [ ] 1.2 Carry the unit through the owner's operations from `OwnedAgent.unit` rather than re-deriving it: stop, recover, status, and anything 1.1 turned up [REQ: the-scope-unit-is-a-stored-fact-not-a-name-derived-from-the-label]
- [ ] 1.3 Keep `scopes.unit_name()` as the start-time chooser only; make it a defect for it to be called with a label that already belongs to a held agent [REQ: the-scope-unit-is-a-stored-fact-not-a-name-derived-from-the-label]
- [ ] 1.4 Test: an agent whose stored unit differs from `unit_name(its label)` is still stopped, recovered and reported correctly — the test must fail if any path re-derives [REQ: the-scope-unit-is-a-stored-fact-not-a-name-derived-from-the-label]

## 2. Rename in the owner

- [ ] 2.1 `AgentOwner.rename(old, new)` — re-key the held map, leave the process, the pty and the scope untouched; return the agent under its new label [REQ: a-framework-held-agent-can-be-renamed-while-it-runs]
- [ ] 2.2 Refuse a rename onto a label another held agent carries, with the holder named in the refusal; a rename to the current label succeeds and changes nothing [REQ: a-rename-refuses-a-name-another-held-agent-carries]
- [ ] 2.3 Refuse a rename for a label the owner does not hold, with a reason that says the name belongs to the runtime [REQ: a-framework-held-agent-can-be-renamed-while-it-runs]
- [ ] 2.4 `rename` over the owner socket protocol + `OwnerClient.rename()` [REQ: a-framework-held-agent-can-be-renamed-while-it-runs]
- [ ] 2.5 Test that the rename does NOT stop, start or resume anything: assert on the scope's `ActiveState` and pid across the call, and that no resume argv is ever built. Mutation-check it — a test that only asserts the new label passes on an implementation that stops and re-creates [REQ: a-framework-held-agent-can-be-renamed-while-it-runs]

## 3. Rename through the API and into everything addressed by name

- [ ] 3.1 `POST /api/fleet/agents/{label}/rename` — addressed by label like `stop`; body carries the new label; refusals come back as themselves, not as 500s [REQ: a-rename-carries-into-everything-that-addresses-the-agent-by-name]
- [ ] 3.2 The old label stops resolving: terminal relay and stop under the old name no longer reach the agent [REQ: a-rename-carries-into-everything-that-addresses-the-agent-by-name]
- [ ] 3.3 The rename updates the durable record's entry for that session, so a later restore brings it back under the new name [REQ: a-rename-carries-into-everything-that-addresses-the-agent-by-name]
- [ ] 3.4 The rename updates `fleet-layout.json` docks that name the old label, under the same conflict-safe write the layout already uses [REQ: a-view-instance-can-be-docked-to-an-edge]
- [ ] 3.5 Test the guard suite's route classification still holds for the new wildcard route (`{label}`), the way the roster route needed narrowing [REQ: a-rename-carries-into-everything-that-addresses-the-agent-by-name]

## 4. The record stores the name the framework holds

- [ ] 4.1 `roster._entry_from` takes the framework's label for that pid instead of `agent.name`; the label source is passed in rather than resolved inside the roster, which must stay free of the owner [REQ: the-framework-records-each-discovered-agent-durably-keyed-on-session-identity]
- [ ] 4.2 An agent with no framework label is recorded with the label explicitly unknown — never backfilled from the discovered name [REQ: the-framework-records-each-discovered-agent-durably-keyed-on-session-identity]
- [ ] 4.3 When the label source cannot be asked, an existing entry keeps its label and a new entry is written unknown; test that an owner outage cannot overwrite a known label [REQ: the-framework-records-each-discovered-agent-durably-keyed-on-session-identity]
- [ ] 4.4 The API's listing passes the labels it already fetched once (`_owned_by_pid`) into the record write, rather than asking the owner a second time [REQ: the-framework-records-each-discovered-agent-durably-keyed-on-session-identity]

## 5. Restore gives the name back, and says which name it gave

- [ ] 5.1 Restore starts each entry under its recorded label [REQ: each-entry-is-restored-by-starting-an-agent-that-resumes-its-session]
- [ ] 5.2 The outcome distinguishes three cases that all read as `started` today: restored under its own name, renamed because the name was held, derived because none was recorded [REQ: each-entry-is-restored-by-starting-an-agent-that-resumes-its-session]
- [ ] 5.3 The restore surface shows which of the three each entry got — a derived name presented as a restored one is the false value this change exists against [REQ: each-entry-is-restored-by-starting-an-agent-that-resumes-its-session]

## 6. One identity on screen, and the rename control

- [ ] 6.1 `_agent_payload` presents one name: the framework's label for a held agent, the runtime's name for a foreign one [REQ: the-surface-offers-rename-where-the-agents-name-is-shown]
- [ ] 6.2 Test that no agent's displayed name can equal another agent's terminal label — the collision measured on 2026-08-21 [REQ: the-surface-offers-rename-where-the-agents-name-is-shown]
- [ ] 6.3 A rename control on the tile of a held agent, starting from the current name; not offered at all for a foreign one [REQ: the-surface-offers-rename-where-the-agents-name-is-shown]
- [ ] 6.4 A refusal is shown on the tile with its reason, and the displayed name does not change [REQ: the-surface-offers-rename-where-the-agents-name-is-shown]
- [ ] 6.5 A docked panel follows a rename with no reload, and the "no running agent with this terminal" state is left intact for a genuinely absent agent [REQ: a-view-instance-can-be-docked-to-an-edge]
- [ ] 6.6 **LOOK at it in the browser** — rename a live agent from the screen and watch: the terminal keeps its history, the tab strip renames, the docked panel follows. A UI change is not done until somebody looked (`.claude/rules/ui-quality.md`); if the browser cannot be reached, this task stays open and says so [REQ: the-surface-offers-rename-where-the-agents-name-is-shown]

## 7. Close the register, and put the lost names back by hand

- [ ] 7.1 Close B-45, B-46, B-47 in `openspec/bugs/README.md` with the commit that fixes each — closed with evidence, never deleted [REQ: the-framework-records-each-discovered-agent-durably-keyed-on-session-identity]
- [ ] 7.2 Operational, not code: identify each currently running restored agent from its transcript, confirm the name with the user, and rename it. The framework cannot derive this mapping — the change delivers the mechanism, the correction is a human act [REQ: a-framework-held-agent-can-be-renamed-while-it-runs]

## Acceptance Criteria (from spec scenarios)

- [ ] AC-1: WHEN an agent held under label `L` with pid `P` is renamed to `N` THEN the operation succeeds, the agent is afterwards held under `N`, and pid `P` is still the live process [REQ: a-framework-held-agent-can-be-renamed-while-it-runs, scenario: a-running-agent-takes-a-new-name-and-keeps-running]
- [ ] AC-2: WHEN an agent is renamed THEN no session is resumed, no scope is stopped or started, and the agent's transcript gains no new session [REQ: a-framework-held-agent-can-be-renamed-while-it-runs, scenario: a-rename-does-not-resume-stop-or-re-create-anything]
- [ ] AC-3: WHEN a rename is requested for an agent whose population is not `started-here` THEN the request is refused with a reason stating the framework does not hold that agent's terminal [REQ: a-framework-held-agent-can-be-renamed-while-it-runs, scenario: an-agent-the-framework-does-not-hold-cannot-be-renamed]
- [ ] AC-4: WHEN an agent started as unit `U` under label `L` is renamed to `N`, and is then stopped THEN unit `U` is the unit that is stopped, and the stop succeeds [REQ: the-scope-unit-is-a-stored-fact-not-a-name-derived-from-the-label, scenario: a-renamed-agent-is-still-addressed-by-its-original-unit]
- [ ] AC-5: WHEN an agent's label is such that deriving a unit name from it would produce something other than its stored unit THEN every operation on that agent still reaches it [REQ: the-scope-unit-is-a-stored-fact-not-a-name-derived-from-the-label, scenario: a-label-whose-derived-unit-name-differs-from-the-stored-one-does-not-lose-the-agent]
- [ ] AC-6: WHEN a rename to `N` is requested while another held agent carries `N` THEN the request is refused, the answer states that `N` is already held, and neither agent's label changes [REQ: a-rename-refuses-a-name-another-held-agent-carries, scenario: a-taken-name-is-refused-with-the-holder-named]
- [ ] AC-7: WHEN an agent held under `L` is renamed to `L` THEN the operation succeeds and nothing changes [REQ: a-rename-refuses-a-name-another-held-agent-carries, scenario: renaming-an-agent-to-the-name-it-already-has-changes-nothing-and-is-not-an-error]
- [ ] AC-8: WHEN an agent is renamed from `L` to `N` THEN the terminal relay and the stop action for `N` reach that agent, and requests under `L` do not [REQ: a-rename-carries-into-everything-that-addresses-the-agent-by-name, scenario: the-terminal-and-the-stop-action-follow-the-new-name]
- [ ] AC-9: WHEN an agent docked to an edge is renamed THEN the panel is still docked to the same edge for the same agent, and does not report a missing agent [REQ: a-rename-carries-into-everything-that-addresses-the-agent-by-name, scenario: a-docked-panel-follows-its-agents-rename]
- [ ] AC-10: WHEN an agent is renamed and the record is written again THEN the entry for that session carries the new label, so a later restore brings it back under that name [REQ: a-rename-carries-into-everything-that-addresses-the-agent-by-name, scenario: the-durable-record-carries-the-new-name]
- [ ] AC-11: WHEN an agent's tile is shown and its population is `started-here` THEN a rename control is available on that tile [REQ: the-surface-offers-rename-where-the-agents-name-is-shown, scenario: a-held-agent-offers-rename]
- [ ] AC-12: WHEN a rename is refused because the name is taken THEN the tile shows the refusal and the reason, and the displayed name is unchanged [REQ: the-surface-offers-rename-where-the-agents-name-is-shown, scenario: a-refusal-is-shown-on-the-tile-not-swallowed]
- [ ] AC-13: WHEN discovery reports an interactive agent with session id `S` and cwd `C`, and the framework holds it under label `L` while the runtime's derived name for it is `D` THEN the record contains an entry keyed `S` carrying `L`, and it does not carry `D` [REQ: the-framework-records-each-discovered-agent-durably-keyed-on-session-identity, scenario: a-discovered-agent-is-recorded]
- [ ] AC-14: WHEN discovery reports an interactive agent the framework holds no label for THEN the entry states its label is unknown, and the derived name is not recorded in its place [REQ: the-framework-records-each-discovered-agent-durably-keyed-on-session-identity, scenario: an-agent-the-framework-does-not-hold-is-recorded-with-no-label]
- [ ] AC-15: WHEN the service that holds agent labels cannot be reached while the record is written THEN an existing entry keeps its label, and a new entry states its label is unknown [REQ: the-framework-records-each-discovered-agent-durably-keyed-on-session-identity, scenario: the-label-cannot-be-asked-for-and-a-recorded-label-is-not-overwritten-by-a-guess]
- [ ] AC-16: WHEN an agent held under `L` is renamed to `N` and the record is written again THEN the entry for its session carries `N` [REQ: the-framework-records-each-discovered-agent-durably-keyed-on-session-identity, scenario: a-renamed-agent-is-recorded-under-its-new-label]
- [ ] AC-17: WHEN an entry recorded under label `L` is resumable, its session is not live, and restore runs THEN an agent is started resuming that session id under label `L`, and the outcome is `started` naming `L` [REQ: each-entry-is-restored-by-starting-an-agent-that-resumes-its-session, scenario: a-resumable-entry-comes-back-as-a-resumed-session]
- [ ] AC-18: WHEN an entry whose label is unknown is restored THEN the agent starts under a derived label and the outcome states the name was derived, not restored [REQ: each-entry-is-restored-by-starting-an-agent-that-resumes-its-session, scenario: an-entry-with-no-recorded-label-says-its-name-was-derived]
- [ ] AC-19: WHEN an entry's recorded label is already held by another agent and the entry is restored THEN the agent starts under a free variant and the outcome reports both the wanted and the used label [REQ: each-entry-is-restored-by-starting-an-agent-that-resumes-its-session, scenario: a-collision-renames-and-reports-it]
- [ ] AC-20: WHEN an agent docked to an edge is lost to a reboot and then restored under its recorded label THEN the docked view holds that agent again, on the same edge [REQ: a-view-instance-can-be-docked-to-an-edge, scenario: a-dock-follows-its-agent-across-a-restore]
- [ ] AC-21: WHEN a docked agent is not running and has not been renamed or restored THEN the panel is kept and states that no running agent has that terminal [REQ: a-view-instance-can-be-docked-to-an-edge, scenario: a-dock-whose-agent-is-genuinely-absent-is-kept-and-says-so]
