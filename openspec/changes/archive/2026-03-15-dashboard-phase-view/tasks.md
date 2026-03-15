## 1. TypeScript Type Extensions

- [x] 1.1 Add `phase?: number` and `depends_on?: string[]` to `ChangeInfo` in `web/src/lib/api.ts`
- [x] 1.2 Add `current_phase?: number` and `phases?: Record<string, { status: string; completed_at?: string; tag?: string }>` to `StateData` in `web/src/lib/api.ts`

## 2. PhaseView Component

- [x] 2.1 Create `web/src/components/PhaseView.tsx` with props: `changes: ChangeInfo[]`, `state: StateData | null`
- [x] 2.2 Implement phase grouping: group changes by `phase` field (default to 1 if undefined), sort phases ascending
- [x] 2.3 Implement phase status derivation: use `state.extras.phases[N].status` when available, otherwise derive from change statuses (all terminal=completed, any running=running, else pending)
- [x] 2.4 Implement phase header: phase number, status indicator icon, progress (done/total), aggregated tokens (sum of input+output), aggregated duration
- [x] 2.5 Implement dependency tree builder: within each phase, identify root changes (no intra-phase `depends_on`), nest children under their dependency parent
- [x] 2.6 Implement change tree rows: indented by tree depth, showing name (monospace), status (color-coded), duration, tokens (input/output), GateBar component
- [x] 2.7 Show "blocked" status annotation when a change is pending and its `depends_on` target is not yet terminal

## 3. Dashboard Integration

- [x] 3.1 Add `'phases'` to the `PanelTab` union type in `web/src/pages/Dashboard.tsx`
- [x] 3.2 Add `{ id: 'phases', label: 'Phases' }` to the tabs array, positioned after 'changes'
- [x] 3.3 Import PhaseView and render it when `activeTab === 'phases'`, passing `changes` and `state`
