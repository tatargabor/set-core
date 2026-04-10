# Agent Page: Discuss Button + English Default + Voice Entry

## Why

The dashboard's Agent tab auto-greets the user the moment the WebSocket connects: the server immediately spawns a `claude -p` subprocess and sends a hard-coded Hungarian greeting prompt (`chat.py:403-405`, `chat.py:442-444`). This has three problems:

1. **Cost and surprise** — every page load costs money and starts a conversation the user may not want. Switching tabs for 2 seconds triggers a fresh agent run.
2. **Language lock-in** — the greeting is hard-coded in Hungarian, but the project's official agent language is English. Users who want English have to explicitly ask for it every session.
3. **Voice is buried** — voice input is only visible once the user starts typing, even though the primary value of the Agent tab for some users is voice-first interaction when a Soniox token is available.

## What Changes

- **Remove auto-start on connect** — WebSocket opens cleanly, no greeting is spawned until the user explicitly requests it.
- **Splash screen with DISCUSS WITH AGENT button** — when no chat history exists, render a centered splash with a large primary "DISCUSS WITH AGENT" button (and a voice entry button next to it when Soniox is available) instead of the empty chat and placeholder.
- **Explicit start message** — clicking the button sends a new `{type: "start"}` WebSocket message; the server then spawns the greeting prompt. Voice entry sends `{type: "start"}` then begins recording; the first user utterance becomes the opening message.
- **Default language: English** — the greeting prompt is rewritten in English ("Say hi and give a short orchestration status summary."). The agent responds in English unless the user writes in another language, which it then mirrors naturally.
- **Voice input default language: English** — `VoiceInput.tsx` defaults new users to `en` (first-run), with the existing `localStorage` preference override respected so returning Hungarian users keep their setting.
- **Splash re-appears on New Session** — after the user clicks "New Session", the splash returns instead of auto-greeting.
- **Move Agent tab to second-to-last position** — reorder the dashboard tab bar so Agent sits just before Battle (the penultimate tab), moving it out of the runtime-state group.

## Capabilities

### Modified Capabilities
- `web-api-server` — chat WebSocket protocol gains an explicit `start` client message; auto-greet on connect is removed.
- `voice-input` — default language changes from Hungarian to English for new users; `localStorage` override preserved.

## Impact

- **`lib/set_orch/chat.py`** — remove auto-greet on connect and on `new_session`; add `start` message handler that triggers the English greeting.
- **`web/src/components/OrchestrationChat.tsx`** — splash screen state, "DISCUSS WITH AGENT" button, voice-first entry button, `startSession` wire-up.
- **`web/src/hooks/useChatWebSocket.ts`** — expose `startSession()` that sends `{type: "start"}`.
- **`web/src/components/VoiceInput.tsx`** — default `language` state to `en` instead of `hu` (localStorage preference still wins).
- **`web/src/pages/Dashboard.tsx`** — reorder `tabs` array so `agent` sits just before `battle` (second-to-last position).
- **Cost / UX** — no more surprise agent runs from tab switches; user controls when a session begins.
