## Why

The wt-web dashboard currently provides read-only monitoring of orchestration runs. When the orchestrator hits a checkpoint, needs a decision, or the user wants to give ad-hoc instructions, they must switch to the terminal. Adding an interactive chat tab with voice input lets the user communicate with an agent directly from the web UI — type or speak, in Hungarian or English — keeping the full orchestration context in one place.

## What Changes

- New **Orchestration** tab in the wt-web dashboard with a real-time agent chat interface
- WebSocket-based bidirectional communication between browser and a spawned Claude Code agent process (server manages agent lifecycle via stdin/stdout bridge)
- **Voice input** via Soniox Web SDK (`@soniox/speech-to-text-web`) — microphone toggle button that streams speech to text in real-time, inserting the transcript into the text input for review before sending
- Language selector (Hungarian / English) for voice recognition
- Soniox API key stored server-side as `SONIOX_API_KEY` env var, served to browser via `GET /api/soniox-key` (keeps key out of JS bundle since dashboard is LAN/Tailscale accessible)
- Backend WebSocket endpoint (`/ws/{project}/chat`) that spawns and manages a Claude Code subprocess, bridging stdin/stdout to WebSocket messages

## Capabilities

### New Capabilities
- `voice-input`: Browser-based speech-to-text input component using Soniox Web SDK with language selection (hu/en), microphone toggle, real-time partial transcription, and editable text output
- `orchestration-chat`: Interactive chat tab in wt-web with WebSocket agent communication, message history display, agent output streaming, and text+voice input

### Modified Capabilities
- `web-dashboard-spa`: Adding new Orchestration tab to the existing tab navigation and routing
- `web-api-server`: Adding `/ws/{project}/chat` WebSocket endpoint for agent subprocess management

## Impact

- **Frontend**: New React components (OrchestrationChat, VoiceInput), new `@soniox/speech-to-text-web` dependency, new route and tab
- **Backend (FastAPI)**: New WebSocket endpoint, subprocess spawning logic for Claude Code agent, lifecycle management (start/stop/cleanup)
- **Environment**: `SONIOX_API_KEY` server env var required for voice input (graceful degradation if absent — voice button hidden, text-only mode)
- **Dependencies**: `@soniox/speech-to-text-web` npm package added to web/package.json
- **Mobile/Tailscale**: Voice input and chat components follow mobile-first responsive patterns from `mobile-responsive-dashboard`. Touch-friendly tap targets, works on mobile Chrome over Tailscale (HTTPS required for remote microphone access)
