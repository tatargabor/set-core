import { useEffect, useState } from 'react'

interface SonioxAvailability {
  /** True once the /api/soniox-key fetch has resolved (success or failure). */
  checked: boolean
  /** True when the Soniox API key was successfully fetched. */
  hasKey: boolean
  /** The API key (or null if unavailable). */
  apiKey: string | null
  /** True when navigator.mediaDevices.getUserMedia is supported in this context. */
  micSupported: boolean
}

let cached: Promise<{ apiKey: string | null }> | null = null

function fetchKey(): Promise<{ apiKey: string | null }> {
  if (!cached) {
    cached = fetch('/api/soniox-key')
      .then(res => (res.ok ? res.json() : Promise.reject(new Error('no key'))))
      .then(data => ({ apiKey: data.api_key as string }))
      .catch(() => ({ apiKey: null }))
  }
  return cached
}

/**
 * Shared availability check for voice input.
 * Used by VoiceInput (the mic button) and by callers that need to know
 * whether to render voice-related UI (e.g. the Agent splash screen).
 */
export function useSonioxAvailable(): SonioxAvailability {
  const [apiKey, setApiKey] = useState<string | null>(null)
  const [checked, setChecked] = useState(false)
  const [micSupported, setMicSupported] = useState(true)

  useEffect(() => {
    let cancelled = false
    fetchKey().then(({ apiKey }) => {
      if (cancelled) return
      setApiKey(apiKey)
      setChecked(true)
    })
    return () => {
      cancelled = true
    }
  }, [])

  useEffect(() => {
    if (!navigator.mediaDevices?.getUserMedia) {
      setMicSupported(false)
    }
  }, [])

  return {
    checked,
    hasKey: apiKey !== null,
    apiKey,
    micSupported,
  }
}
