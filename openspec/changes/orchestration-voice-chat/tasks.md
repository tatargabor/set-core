## 1. Setup & Dependencies

- [?] 1.1 Configure Soniox API key as `SONIOX_API_KEY` environment variable for the FastAPI server [input:SONIOX_API_KEY]
- [x] 1.2 Add `@soniox/speech-to-text-web` dependency to `web/package.json`

### Manual: 1.1 — Configure Soniox API key

1. The user already has the API key from the Soniox Console
2. Add `SONIOX_API_KEY=<key>` to the server's environment (e.g., shell profile, systemd unit, or `.env` file used by the FastAPI server)
3. Never commit API keys to git
4. Restart the FastAPI server after adding

## 2. Backend — Soniox Key & Chat WebSocket

- [x] 2.1 Add `GET /api/soniox-key` endpoint — returns `{ "api_key": "<value>" }` from `SONIOX_API_KEY` env var, or 404 if not set
- [x] 2.2 Add `/ws/{project}/chat` WebSocket endpoint to the FastAPI server that accepts connections and manages message routing
- [x] 2.3 Implement agent subprocess spawning — spawn `claude --output-format stream-json` in the project directory on first message
- [x] 2.4 Implement stdin bridge — write user messages from WebSocket to subprocess stdin
- [x] 2.5 Implement stdout parser — read subprocess stdout line-by-line, parse stream-json events, map to chat protocol (`assistant_text`, `tool_use`, `tool_result`, `assistant_done`, `status`)
- [x] 2.6 Implement subprocess lifecycle — track one subprocess per project, reuse on reconnect, SIGTERM on stop, cleanup on server shutdown
- [x] 2.7 Add subprocess stderr logging to server log
- [x] 2.8 Handle subprocess exit — notify client with error event and close WebSocket

## 3. Frontend — Orchestration Chat Component

- [ ] 3.1 Create `OrchestrationChat.tsx` component with message history display (user messages right-aligned, agent messages left-aligned with markdown support)
- [ ] 3.2 Add chat WebSocket hook (`useChatWebSocket.ts`) — connect to `/ws/{project}/chat`, send messages, receive events, auto-reconnect
- [ ] 3.3 Add text input with Send button — Enter to send, Shift+Enter for newline, disabled during agent processing. Mobile: 44px min touch targets
- [ ] 3.4 Implement agent output streaming — progressive text display from `assistant_text` events
- [ ] 3.5 Add tool use display — collapsible blocks showing tool name and input/output summary for `tool_use`/`tool_result` events
- [ ] 3.6 Add agent status indicator — thinking/responding/tool-use/idle states with animation
- [ ] 3.7 Add connection status indicator — green/red dot for WebSocket connected/disconnected
- [ ] 3.8 Add session controls — "New Session" button to stop subprocess and clear history
- [ ] 3.9 Implement auto-scroll with manual scroll preservation and "Jump to bottom" button

## 4. Frontend — Voice Input Component

- [ ] 4.1 Create `VoiceInput.tsx` component with microphone toggle button (idle/recording states, 44px min touch target)
- [ ] 4.2 Fetch Soniox API key from `GET /api/soniox-key` on mount — hide voice controls if 404
- [ ] 4.3 Integrate Soniox Web SDK — initialize `SonioxClient` with fetched key, start/stop recording on button click
- [ ] 4.4 Implement real-time partial transcription — stream Soniox partial result tokens into the textarea
- [ ] 4.5 Implement final transcript — on stop, place final text in textarea as editable content
- [ ] 4.6 Add language selector dropdown (HU / EN) with localStorage persistence, default HU. 44px touch target on mobile
- [ ] 4.7 Add recording duration timer display (e.g., "0:12") next to mic button while recording
- [ ] 4.8 Handle microphone permission denial — show brief error, return to idle state
- [ ] 4.9 Handle insecure context (non-HTTPS remote access) — detect `getUserMedia` unavailable, hide voice controls, text-only fallback

## 5. Frontend — Dashboard Integration

- [ ] 5.1 Add "Orchestration" tab to Dashboard.tsx tab navigation
- [ ] 5.2 Wire OrchestrationChat component into the tab content area with VoiceInput integrated into the input row
- [ ] 5.3 Verify existing Vite proxy covers `/ws/{project}/chat` (already proxies `/ws` → localhost:7400)

## 6. Testing

- [ ] 6.1 Manual test: text-only chat — send message, receive streamed response, verify message history
- [ ] 6.2 Manual test: voice input — record speech in Hungarian, verify partial transcript, edit, send
- [ ] 6.3 Manual test: language switch — toggle HU/EN, verify transcription language changes
- [ ] 6.4 Manual test: graceful degradation — start server without `SONIOX_API_KEY`, verify mic button hidden, text chat works
- [ ] 6.5 Manual test: session lifecycle — start session, stop session, start new session
- [ ] 6.6 Manual test: reconnection — refresh page while agent is running, verify reconnection to existing subprocess
- [ ] 6.7 Manual test: mobile over Tailscale — open dashboard on phone via Tailscale HTTPS, verify voice input and chat work with touch
- [ ] 6.8 Manual test: insecure context fallback — open via HTTP on non-localhost, verify mic hidden but text chat works
