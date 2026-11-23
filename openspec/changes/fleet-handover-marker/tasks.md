## 1. Detection (Layer 1, `lib/set_orch/fleet/state.py`)

- [x] 1.1 `_HANDOVER_RE` + `HANDOVER_NEED_INPUT` / `HANDOVER_ALL_DONE`, the family's marker pattern
- [x] 1.2 `_last_handover(lines)`: the closing stretch of the last turn; a person's reply clears it
- [x] 1.3 `AgentState.handover`, set on the quiet path only
- [x] 1.4 `_compose_attention`: `need_input` raises `input` / `background` to `prompt`

## 2. API (`lib/set_orch/api/fleet.py`)

- [x] 2.1 `handover` on the list payload and the single-agent payload

## 3. Surface (`web/src`)

- [x] 3.1 `FleetAgent.handover`, `AttentionAgent.handover`, `isAskingYou`
- [x] 3.2 `tally.askingNow` and the jump-to-asker list count `need_input`
- [x] 3.3 `StateLine`: `needs your input` (sky) for a `need_input` turn, parked when cold

## 4. Tests

- [x] 4.1 `tests/unit/test_fleet_handover_marker.py` — 14 cases: emphasis forms, mid-sentence, reply clears, running turn, earlier stretch, multi-entry close, busy record, ALL DONE
- [x] 4.2 `web/tests/unit/fleetTabBadge.test.ts` and `fleetInputAttentionSurface.test.tsx` — the three positive cases are red on the reverted source (stash-and-rerun)

## 5. Live check

- [x] 5.1 After a `set-web` restart, `GET /api/fleet/agents` carried `handover: need_input`, `attention: prompt` for a live agent whose turn ended on a `NEED INPUT:` line
- [x] 5.2 Looked at the fleet in the browser: the tile read `needs your input 4m`, the project row carried `Q1` and the tab title `❓ SET (1)`
