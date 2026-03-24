# Web Frontend Rules

## Action buttons must have loading state

Every button that triggers an async operation (API call, process start/stop) MUST:

1. **Disable immediately on click** — prevent double-click/rapid re-submission
2. **Show loading text** — change label to indicate action in progress (e.g., "Start" → "Starting…")
3. **Use `disabled:cursor-not-allowed`** — visual cue that the button is inactive
4. **Re-enable after response** — whether success or failure, always restore the button

Pattern:
```tsx
const [busy, setBusy] = useState(false)
const act = async (fn: () => Promise<unknown>) => {
  setBusy(true)
  try { await fn() }
  finally { setBusy(false) }
}
<button disabled={busy} onClick={() => act(() => apiCall())}>
  {busy ? 'Working…' : 'Do Thing'}
</button>
```

## Polling state updates

When UI polls for status (setInterval), avoid unnecessary re-renders:
- Compare JSON-serialized response with a ref before calling setState
- This prevents flickering and wasted renders on unchanged data
