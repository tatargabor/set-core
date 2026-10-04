export type FwPrompt = { slot: string; label: string } | null

declare module 'claude-code' {
  interface PluginState {
    'feed-watch-pane': { prompt: FwPrompt; instance: string }
  }
}
