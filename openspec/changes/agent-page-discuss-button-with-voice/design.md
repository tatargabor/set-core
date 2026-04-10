# Design: Agent Page Discuss Button + Voice Entry

## Context

`OrchestrationChat.tsx` is the React component rendered in the dashboard's Agent tab. It opens a WebSocket to `/ws/{project}/chat`, which is served by `ChatSession` in `lib/set_orch/chat.py`. On connect the server replays history and — if history is empty — immediately schedules a Claude subprocess with a hard-coded Hungarian greeting prompt.

This was convenient during initial development ("just show me something when I open the tab") but is now actively harmful: users pay for an LLM run every time they open the Agent tab, the greeting is locked to Hungarian while the rest of the system defaults to English, and voice-first workflows (Soniox) have no prominent entry point.

## Goals / Non-Goals

**Goals:**
- No agent subprocess spawned until the user explicitly asks for one.
- Prominent "DISCUSS WITH AGENT" entry point on a splash screen when no chat history exists.
- Voice entry button on the splash screen when a Soniox token is available, so users can initiate by speaking.
- English is the default greeting language. Users can still write in any language — the agent mirrors naturally.
- Returning users with chat history see the existing chat view immediately (no splash).

**Non-Goals:**
- Changing the agent's underlying tool set or system prompt (beyond the greeting string).
- Persisting start preferences across projects (localStorage stays per-browser).
- Adding a full "language picker" — English default + existing `hu`/`en` voice toggle is enough.
- Re-designing the chat view after the splash disappears.

## Decisions

### 1. New explicit `start` WebSocket message

**Choice:** Add a new client→server message type `{type: "start"}`. The server spawns the greeting subprocess only in response to this message (or to a normal user `message`).

**Why not reuse `message` with a sentinel string?** Overloading the content channel would couple the client and server to a magic value. A distinct type keeps the protocol self-describing and makes future changes (e.g., different greeting modes) cleaner.

**Alternatives considered:**
- Send an empty `message` — ambiguous with "user pressed Send on an empty textarea" (which we intentionally ignore).
- Query parameter on the WebSocket URL — adds reconnect complications when the user wants to start fresh.

### 2. Frontend splash state derived from history + session status

**Choice:** `showSplash = messages.length === 0 && agentStatus === 'idle'`. No separate boolean state that can drift.

**Why derived?** The source of truth for "is there a conversation in progress" is the messages array, which is already synced via `history_replay` on connect. Adding a parallel boolean would create race conditions with replay/reconnect. When `session_cleared` arrives or the user clicks "New Session", messages clear and the splash naturally reappears.

### 3. Voice entry button: optional, mounted next to the main button

**Choice:** On the splash, render the "DISCUSS WITH AGENT" primary button. If `VoiceInput` determines a Soniox key is available, render a secondary voice button beside (or below on narrow screens) it. Clicking voice sends the `start` message *and* opens the recorder so the first utterance becomes the opening user message.

**Why reuse `VoiceInput`?** The mic button, language toggle, and recording state are already encapsulated. For the splash variant we pass a larger size prop / wrapping container; the underlying behavior (capture → `onTranscript`) is identical.

**Alternatives considered:**
- Auto-record on splash — hostile UX (mic activates without consent).
- Separate "voice session" mode — unnecessary; a voice-initiated session should be structurally identical to a text-initiated one afterwards.

### 4. English greeting prompt, user still free to write Hungarian

**Choice:** The server's greeting message becomes "Say hi and give a short orchestration status summary." (English). The agent's base system prompt already supports multi-lingual interaction — if the user follows up in Hungarian, the agent will naturally switch.

**Why not read the user's browser locale?** Setting the default to English aligns with the rest of the set-core agent ecosystem (log messages, chat context builder, CLI output). Users who prefer Hungarian can write their first message in Hungarian and the conversation continues in Hungarian. This is simpler than wiring browser locale through the WebSocket.

### 5. VoiceInput default language: `en` (localStorage override respected)

**Choice:** `useState(() => (localStorage.getItem('set-voice-lang') as Language) || 'en')` — same pattern as today, but fallback is `en`.

**Why?** Consistent with the English-by-default decision above. Returning users who previously selected Hungarian still have `localStorage['set-voice-lang'] === 'hu'` and keep their preference. Only brand-new browsers start in English.

## Risks / Trade-offs

- **[Risk] Existing users expect the auto-greeting** → Mitigation: the splash button is large and labeled clearly. A single click restores the previous behavior. Worst case is one confused click.
- **[Risk] Returning Hungarian-speaking voice users get surprise English** → Non-issue: `localStorage['set-voice-lang']` is persisted. Only first-time users on a given browser see English.
- **[Trade-off] Splash vs. auto-start** → We accept one extra click in exchange for zero surprise spawns. For a dashboard viewed dozens of times per session, this saves real money.
- **[Trade-off] English default greeting for Hungarian primary users** → The user explicitly asked for this behavior. Mitigation: user can reply in Hungarian and the agent follows.

## Open Questions

None — scope fully specified by the user request.
