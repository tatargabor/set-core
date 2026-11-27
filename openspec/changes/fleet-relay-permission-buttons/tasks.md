## 1. Route

- [x] 1.1 `/api/fleet/question-relay/{id}/answer` accepts a permission prompt with exactly `Allow` or `Deny`, no teach; refuses everything else (`lib/set_orch/api/fleet_relay_teach.py`)
- [x] 1.2 Tests: six refused shapes, both buttons written and read back through `permission_output`, teach refused (`tests/unit/test_fleet_relay_teach_api.py`). Checked against HEAD's route with `.pyc` cleared: 3 fail, restored: 25 pass

## 2. Board

- [x] 2.1 `PERMISSION_ANSWERS` and `permissionButtons()` (`web/src/lib/fleetRelayBoard.ts`); status and wait texts name the board (`fleetRelayBoard.ts`, `fleetRelayTeach.ts`)
- [x] 2.2 Allow (emerald) / Deny (red) buttons on a permission row, in both the decider-record and the no-record layout (`web/src/components/FleetRelayBoard.tsx`)
- [x] 2.3 Unit test for `permissionButtons` (`web/tests/unit/fleetRelayBoard.test.ts`); `tsc -b` clean

## 3. Looked at

- [x] 3.1 2026-11-27, live dashboard after `set-web` restart, a temporary permission record (removed after): the row showed Allow / Deny beside the "permission" status; Deny turned the row "answered — Sent: «Deny»" and the answer store held `{"valasz": "Deny"}`
- [ ] 3.2 A real permission prompt answered from the board (the owner's next one)

## 4. Cross-reference

- [x] 4.1 `fleet-relay-board` (unarchived) said a permission row shows no answer controls; its sentence now points here, so archiving either order leaves no contradiction
