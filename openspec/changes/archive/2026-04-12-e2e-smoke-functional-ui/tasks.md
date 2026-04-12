## 1. Backend — always save smoke stats

- [x] 1.1 merger.py: save `smoke_e2e_output` on success too (currently only on failure at L1167) — move to after the if/else block so both paths save it
- [x] 1.2 merger.py: save `smoke_test_count`, `own_test_count`, `inherited_file_count` after two-phase detection (after L1124)
- [x] 1.3 merger.py: when no two-phase (single-phase fallback), save `own_test_count` = total spec count, `smoke_test_count` = 0

## 2. Frontend — ChangeInfo interface

- [x] 2.1 api.ts: add `smoke_e2e_output?: string`, `smoke_test_count?: number`, `own_test_count?: number`, `inherited_file_count?: number` to ChangeInfo

## 3. Frontend — E2EPanel rewrite

- [x] 3.1 DigestView.tsx: parse smoke output separately via `parseE2EOutput(c.smoke_e2e_output)` alongside the existing `parseE2EOutput(c.e2e_output)`
- [x] 3.2 DigestView.tsx: render two sections per change — "SMOKE (inherited)" with smoke badge/time/count, "FUNCTIONAL (own)" with own badge/time/count
- [x] 3.3 DigestView.tsx: update summary line to include smoke/functional breakdown counts
- [x] 3.4 DigestView.tsx: show timing per section (`gate_e2e_smoke_ms` / `gate_e2e_own_ms`) formatted as seconds
