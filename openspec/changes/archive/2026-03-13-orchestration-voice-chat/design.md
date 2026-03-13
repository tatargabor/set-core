## Context

The wt-web dashboard is a React 19 + Vite 7 SPA that monitors orchestration runs via a FastAPI backend on port 7400. It already has WebSocket infrastructure (`/ws/{project}/stream`) for state and log streaming, plus REST endpoints for read/write operations. Currently all user interaction is read-only monitoring with approve/stop/skip actions — there is no way to send freeform instructions to an agent from the UI.

**Important context**: The `mobile-responsive-dashboard` change made the server bind to `0.0.0.0` by default, meaning the dashboard is accessible from other devices on the LAN or Tailscale VPN. This means the chat endpoint and Soniox API key (baked into the JS bundle) are also reachable from phones and other machines on the private network. The mobile-responsive change also added responsive layouts (sidebar drawer, card views, touch targets), so voice input components must follow the same mobile-first patterns.

The Soniox Web SDK (`@soniox/speech-to-text-web`) provides browser-based real-time speech-to-text in 60+ languages (including Hungarian). It uses a WebSocket connection from the browser directly to Soniox servers, with sub-200ms latency.

## Goals / Non-Goals

**Goals:**
- Add an Orchestration tab where the user can have an interactive text conversation with an agent
- Enable voice input via Soniox as an alternative to typing
- Stream agent output in real-time to the UI
- Support Hungarian and English voice recognition with runtime language switching

**Non-Goals:**
- Voice output / text-to-speech (read-only text output)
- Multi-user / concurrent agent sessions (single user, single session)
- Persistent chat history across page reloads (ephemeral, tied to agent process lifetime)
- Agent-initiated voice (agent always responds in text)
- Phone/VoIP integration
- Soniox temporary key rotation (server-side key endpoint is sufficient for private network)

## Decisions

### D1: Agent communication via new WebSocket endpoint

**Decision:** Add `/ws/{project}/chat` WebSocket endpoint that spawns a Claude Code subprocess and bridges stdin/stdout.

**Alternatives considered:**
- *wt-msg polling*: Existing message system, but 15-30s round-trip latency per exchange makes interactive chat impractical
- *HTTP long-polling*: Simpler than WebSocket but cannot stream partial agent output
- *Shared terminal session (tmux attach)*: Complex, not embeddable in web UI

**Rationale:** WebSocket provides real-time bidirectional streaming. The server spawns `claude` as a subprocess with `--output-format stream-json`, reads stdout line-by-line, and forwards JSON events to the browser. User messages arrive via WebSocket and are written to the process stdin.

### D2: Agent subprocess lifecycle

**Decision:** One agent subprocess per project, managed by the FastAPI server.

- `connect` → if no subprocess exists for this project, spawn `claude --output-format stream-json` in the project directory
- `disconnect` → subprocess stays alive (user may reconnect)
- Explicit `stop` message or server shutdown → SIGTERM the subprocess
- If subprocess exits on its own → notify client via WebSocket close with reason

**Rationale:** Keeping the subprocess alive on disconnect avoids losing context when the user refreshes the page. The subprocess is lightweight (single claude process).

### D3: Soniox integration — server-side key via REST endpoint

**Decision:** The Soniox API key is stored server-side (environment variable `SONIOX_API_KEY`). The FastAPI server exposes `GET /api/soniox-key` which returns the key to the browser on request. The browser uses `@soniox/speech-to-text-web` with this key.

**Alternatives considered:**
- *`VITE_SONIOX_API_KEY` build-time env var*: Simpler, but since the server binds to `0.0.0.0` (Tailscale/LAN accessible), the key would be baked into the JS bundle visible to any device on the network. Acceptable for single-user dev tool, but server-side is barely more work and avoids key-in-bundle.
- *Soniox temporary key API*: Best practice for production apps, but requires a separate Soniox endpoint call from the backend. Overkill for a private network tool.
- *Server-side transcription*: Would require streaming audio to our server first — adds latency and complexity.
- *Browser Web Speech API*: Free, no API key, but poor Hungarian support and inconsistent across browsers.

**Rationale:** Server-side key keeps the API key out of the JS bundle. The endpoint is still only reachable on the private network. If the key is not configured, the endpoint returns 404 and the frontend hides voice input (graceful degradation). This also means the key doesn't need to be present at build time — works with production builds served by the FastAPI server.

### D4: Voice input UX — push-to-talk with editable output

**Decision:** Microphone toggle button next to the text input. Click to start recording, click again to stop. Partial transcription streams into the textarea in real-time. After stopping, the user can edit the text before sending.

**Alternatives considered:**
- *Auto-send on silence detection*: Risky — may send incomplete thoughts
- *Voice-only mode*: Too restrictive — users need to type sometimes
- *Hold-to-talk*: Awkward for longer dictation

**Rationale:** This gives the user full control. They see what Soniox heard, can fix errors, and send when ready. The partial results provide immediate feedback that recording is working.

### D5: Language selection — runtime toggle

**Decision:** Small dropdown next to the mic button with "HU" / "EN" options. Changes the `languageHints` parameter passed to Soniox on the next recording session. Default: Hungarian.

**Rationale:** The user works primarily in Hungarian but may switch to English for technical terms or code-related instructions. Runtime switching (not per-word) keeps the UX simple.

### D6: Chat message protocol

**Decision:** WebSocket messages between browser and server use a simple JSON envelope:

```
Browser → Server:
  { "type": "message", "content": "user text here" }
  { "type": "stop" }

Server → Browser:
  { "type": "assistant_text", "content": "partial text..." }
  { "type": "assistant_done" }
  { "type": "tool_use", "tool": "Bash", "input": "..." }
  { "type": "tool_result", "output": "..." }
  { "type": "error", "message": "..." }
  { "type": "status", "status": "thinking" | "responding" | "idle" }
```

**Rationale:** Maps directly to Claude Code's `stream-json` output format. The browser doesn't need to understand every event type — unknown types are logged and ignored. This is forward-compatible as Claude Code adds new event types.

### D7: Mobile and Tailscale compatibility

**Decision:** Voice input and chat components follow the mobile-first responsive patterns established by the `mobile-responsive-dashboard` change. The mic button and language selector use 44px minimum touch targets. On mobile viewports (<768px), the input row stacks vertically if needed. Voice recording works on mobile Chrome (Android) since Soniox Web SDK uses standard `getUserMedia` API.

**Rationale:** Since the server binds to `0.0.0.0`, users access the dashboard from phones over Tailscale. Voice input from a phone is a natural and high-value use case — dictate instructions while away from the desktop.

## Risks / Trade-offs

- **[Agent subprocess leak]** → If the server crashes, the spawned claude process becomes orphaned. Mitigation: on server startup, check for and clean up orphan processes. Also set a process group so SIGTERM propagates.
- **[Soniox API costs]** → Real-time transcription is billed per minute of audio. Mitigation: push-to-talk (not always-on) limits usage to intentional recording. Display recording duration in the UI.
- **[Context window exhaustion]** → Long chat sessions may exhaust the agent's context. Mitigation: show token usage if available from stream-json events. User can stop and start a new session.
- **[Hungarian transcription quality]** → Soniox claims 60+ languages but Hungarian accuracy may vary. Mitigation: editable textarea lets user fix errors before sending. Run a PoC test before deep integration.
- **[Missing API key]** → If `SONIOX_API_KEY` is not set on the server, voice features are unavailable. Mitigation: graceful degradation — `/api/soniox-key` returns 404, frontend hides mic button, text-only input. No error, no broken UI.
- **[Mobile microphone access over Tailscale]** → Browsers require HTTPS for `getUserMedia` except on `localhost`. Tailscale IPs (100.x.x.x) are not localhost. Mitigation: Tailscale provides MagicDNS with HTTPS certificates via `tailscale cert`. If HTTPS is not available, voice input won't work on remote devices but text chat still works. Document this in setup notes.
- **[Chat WebSocket exposed on LAN]** → The `/ws/{project}/chat` endpoint can spawn agent processes from any device on the network. Mitigation: this is a single-user dev tool on a private network — same trust model as the existing approve/stop endpoints already exposed on `0.0.0.0`.
