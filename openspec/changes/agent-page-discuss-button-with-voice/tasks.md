## 1. Backend: remove auto-start, add explicit `start` message

- [x] 1.1 In `lib/set_orch/chat.py`, delete the auto-greet block at `websocket_chat()` that runs on empty-history connect (currently lines ~402-405) [REQ: chat-websocket-endpoint, scenario: client-connects-with-empty-history]
- [x] 1.2 In `lib/set_orch/chat.py`, delete the auto-greet block after `session_cleared` in the `new_session` handler (currently lines ~442-444) [REQ: chat-websocket-endpoint, scenario: client-sends-new_session]
- [x] 1.3 Add a `start` message handler in `websocket_chat()` that: refuses if `session.status == "running"` (send error), otherwise sets `session.status = "running"` and schedules `session.send_message("Say hi and give a short orchestration status summary.")` [REQ: chat-websocket-endpoint, scenarios: client-sends-start, client-sends-start-while-already-running]
- [x] 1.4 Log the `start` event at INFO with project name for debugging [REQ: chat-websocket-endpoint]
- [x] 1.5 Confirm no other server-side path calls `send_message` with the Hungarian greeting string (grep for "Köszönj") [REQ: chat-websocket-endpoint]
- [x] 1.6 Update `lib/set_orch/chat_context.py` to emit English role + status + commands sections and instruct the agent to default to English with language mirroring (discovered during implementation: the old Hungarian system prompt would override the English greeting) [REQ: chat-websocket-endpoint, scenario: client-sends-start]

## 2. Frontend: WebSocket hook exposes `startSession`

- [x] 2.1 In `web/src/hooks/useChatWebSocket.ts`, add a `startSession` callback that calls `send({ type: 'start' })` [REQ: agent-tab-splash-screen-with-discuss-with-agent-button]
- [x] 2.2 Return `startSession` from the hook alongside `sendMessage`, `stopAgent`, `newSession` [REQ: agent-tab-splash-screen-with-discuss-with-agent-button]

## 3. Frontend: OrchestrationChat splash screen

- [x] 3.1 In `web/src/components/OrchestrationChat.tsx`, derive `showSplash = messages.length === 0 && agentStatus === 'idle' && !voiceEntryMode` (no separate boolean for the splash itself; voiceEntryMode is a short-lived overlay state) [REQ: agent-tab-splash-screen-with-discuss-with-agent-button, scenario: splash-on-empty-session]
- [x] 3.2 When `showSplash` is true, render a centered splash instead of the placeholder "Send a message..." text [REQ: agent-tab-splash-screen-with-discuss-with-agent-button]
- [x] 3.3 Splash contains a large primary button labeled "DISCUSS WITH AGENT"; clicking calls `startSession()` from the hook [REQ: agent-tab-splash-screen-with-discuss-with-agent-button, scenario: click-starts-the-session]
- [x] 3.4 Hide the input textarea, voice button, and Send button while `showSplash` is true [REQ: agent-tab-splash-screen-with-discuss-with-agent-button]
- [x] 3.5 After click, the incoming `status: thinking` event flips `agentStatus` away from idle, so splash disappears automatically — verified via existing `onEvent` reducer [REQ: agent-tab-splash-screen-with-discuss-with-agent-button, scenario: splash-hidden-when-history-exists]
- [x] 3.6 Ensure splash reappears after "New Session" (messages cleared → splash condition holds again) [REQ: agent-tab-splash-screen-with-discuss-with-agent-button, scenario: splash-returns-after-new-session]

## 4. Frontend: Voice entry button on splash

- [x] 4.1 Extracted Soniox availability detection into `web/src/hooks/useSonioxAvailable.ts` — shared between `VoiceInput.tsx` and the splash in `OrchestrationChat.tsx` [REQ: voice-entry-button-on-splash-screen]
- [x] 4.2 On the splash, when `hasSonioxKey && micSupported`, render a secondary voice entry button (microphone icon + "Speak to agent" label) below "DISCUSS WITH AGENT" [REQ: voice-entry-button-on-splash-screen, scenario: voice-button-visible-when-soniox-configured]
- [x] 4.3 Voice button click enters `voiceEntryMode`, which mounts `VoiceInput` with `autoStart` so recording begins immediately. On `onTranscript`, the transcribed text is sent as a normal user `message` and `voiceEntryMode` is cleared. **Design deviation from task draft**: the voice path does NOT also send `{type: "start"}` — doing both would race (server spawns greeting AND tries to handle the user message in parallel). Voice-entry skips the greeting and goes straight to the user's first utterance [REQ: voice-entry-button-on-splash-screen, scenario: voice-entry-starts-recording]
- [x] 4.4 Voice button is hidden when `hasSonioxKey === false` (404 from `/api/soniox-key`) [REQ: voice-entry-button-on-splash-screen, scenario: voice-button-hidden-when-soniox-missing]
- [x] 4.5 Voice button is hidden when `navigator.mediaDevices.getUserMedia` is undefined [REQ: voice-entry-button-on-splash-screen, scenario: voice-button-hidden-when-mic-unavailable]
- [x] 4.6 Splash layout is mobile-friendly: stacked vertically, 88px min-height on primary button, 56px on voice button (well above 44px touch target) [REQ: voice-entry-button-on-splash-screen]

## 5. Frontend: VoiceInput default language → English

- [x] 5.1 In `web/src/components/VoiceInput.tsx`, changed the `useState<Language>` initializer fallback from `'hu'` to `'en'` [REQ: language-selector, scenario: default-language-for-new-users]
- [x] 5.2 Verified `localStorage.getItem('set-voice-lang')` still wins when set (returning users preserved) [REQ: language-selector, scenario: returning-user-preference-preserved]

## 6. Frontend: Move Agent tab to second-to-last position

- [x] 6.1 In `web/src/pages/Dashboard.tsx`, moved the `{ id: 'agent', label: 'Agent' }` entry out of the runtime-state group and placed it immediately before the `battle` tab in the `tabs` array [REQ: agent-tab-placement-in-dashboard-tab-bar, scenario: default-tab-order-with-all-optional-tabs-visible]
- [x] 6.2 Verified the reorder holds when optional tabs (`digest`, `audit`, `plan`) are hidden — visible order still ends with `... learnings, agent, battle` [REQ: agent-tab-placement-in-dashboard-tab-bar, scenario: tab-order-with-optional-tabs-hidden]

## 7. Build and smoke test

- [x] 7.1 Ran `pnpm build` in `web/` — build succeeded (2458 modules transformed, no TS errors) [REQ: agent-tab-splash-screen-with-discuss-with-agent-button]
- [ ] 7.2 Open the Agent tab on a project with no prior chat history — verify splash appears and no subprocess spawns (check logs for no `Spawning claude` on connect) [REQ: chat-websocket-endpoint, scenario: client-connects-with-empty-history]
- [ ] 7.3 Click "DISCUSS WITH AGENT" — verify server logs `Spawning claude` and agent greets in English [REQ: chat-websocket-endpoint, scenario: client-sends-start]
- [ ] 7.4 Click "New Session" — verify splash returns and no subprocess spawns until next click [REQ: chat-websocket-endpoint, scenario: client-sends-new_session]
- [ ] 7.5 With `SONIOX_API_KEY` set, verify voice entry button appears on splash; without it, verify only "DISCUSS WITH AGENT" is shown [REQ: voice-entry-button-on-splash-screen]
- [ ] 7.6 Fresh browser (cleared localStorage): verify voice language selector defaults to EN [REQ: language-selector, scenario: default-language-for-new-users]
- [ ] 7.7 Verify tab bar order: rightmost two tabs are `Agent` then `Battle`, both with optional tabs visible and hidden [REQ: agent-tab-placement-in-dashboard-tab-bar]

## Acceptance Criteria (from spec scenarios)

- [x] AC-1: WHEN WS connects with empty history THEN server does NOT spawn claude; splash is shown — implemented by removing auto-greet block in `chat.py websocket_chat()` and adding splash render gated on `messages.length === 0 && agentStatus === 'idle'` in `OrchestrationChat.tsx` [REQ: chat-websocket-endpoint, scenario: client-connects-with-empty-history]
- [x] AC-2: WHEN WS connects with existing history THEN splash is not shown; messages render — derivation `showSplash = messages.length === 0 && ...` yields false as soon as `history_replay` populates messages [REQ: agent-tab-splash-screen-with-discuss-with-agent-button, scenario: splash-hidden-when-history-exists]
- [x] AC-3: WHEN user clicks "DISCUSS WITH AGENT" THEN `{type: "start"}` is sent and agent greets in English — `handleDiscussClick` calls `startSession()`, server handler spawns `send_message("Say hi and give a short orchestration status summary.")`, and `chat_context.py` role section instructs English-by-default [REQ: chat-websocket-endpoint, scenario: client-sends-start]
- [x] AC-4: WHEN user sends `new_session` THEN server clears state and does NOT auto-greet — removed the auto-greet block from the `new_session` branch of `websocket_chat()` [REQ: chat-websocket-endpoint, scenario: client-sends-new_session]
- [x] AC-5: WHEN Soniox key available THEN voice entry button is rendered on splash — gated on `hasSonioxKey && micSupported` from `useSonioxAvailable()` [REQ: voice-entry-button-on-splash-screen, scenario: voice-button-visible-when-soniox-configured]
- [x] AC-6: WHEN Soniox key missing THEN only "DISCUSS WITH AGENT" is rendered — `hasSonioxKey === false` collapses the voice button [REQ: voice-entry-button-on-splash-screen, scenario: voice-button-hidden-when-soniox-missing]
- [x] AC-7: WHEN localStorage has no `set-voice-lang` THEN voice selector defaults to EN — fallback changed from `'hu'` to `'en'` in `VoiceInput.tsx` [REQ: language-selector, scenario: default-language-for-new-users]
- [x] AC-8: WHEN localStorage has `set-voice-lang=hu` THEN voice selector stays on HU — initializer still reads `localStorage.getItem('set-voice-lang')` first [REQ: language-selector, scenario: returning-user-preference-preserved]
- [x] AC-9: WHEN dashboard tabs render THEN rightmost two visible tabs are `agent` then `battle` — `tabs` array reordered in `Dashboard.tsx`; `battle` is always last, `agent` is now directly before it [REQ: agent-tab-placement-in-dashboard-tab-bar]
