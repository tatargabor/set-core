import { useState, useEffect, useRef, useCallback } from 'react'

interface Props {
  onTranscript: (text: string) => void
  onPartial: (text: string) => void
  disabled?: boolean
}

type Language = 'hu' | 'en'

export default function VoiceInput({ onTranscript, onPartial, disabled }: Props) {
  const [apiKey, setApiKey] = useState<string | null>(null)
  const [keyChecked, setKeyChecked] = useState(false)
  const [recording, setRecording] = useState(false)
  const [language, setLanguage] = useState<Language>(() => {
    return (localStorage.getItem('set-voice-lang') as Language) || 'hu'
  })
  const [duration, setDuration] = useState(0)
  const [error, setError] = useState<string | null>(null)
  const [micAvailable, setMicAvailable] = useState(true)

  const clientRef = useRef<any>(null)
  const timerRef = useRef<ReturnType<typeof setInterval> | null>(null)
  const finalTextRef = useRef('')
  const partialRef = useRef('')

  // Check if Soniox API key is available
  useEffect(() => {
    fetch('/api/soniox-key')
      .then(res => {
        if (res.ok) return res.json()
        throw new Error('No key')
      })
      .then(data => {
        setApiKey(data.api_key)
        setKeyChecked(true)
      })
      .catch(() => {
        setApiKey(null)
        setKeyChecked(true)
      })
  }, [])

  // Check if getUserMedia is available (HTTPS requirement)
  useEffect(() => {
    if (!navigator.mediaDevices?.getUserMedia) {
      setMicAvailable(false)
    }
  }, [])

  // Save language preference
  useEffect(() => {
    localStorage.setItem('set-voice-lang', language)
  }, [language])

  const stopRecording = useCallback(() => {
    if (timerRef.current) {
      clearInterval(timerRef.current)
      timerRef.current = null
    }

    if (clientRef.current) {
      try {
        clientRef.current.stop()
      } catch {
        // ignore stop errors
      }
    }

    setRecording(false)
    // onFinished callback handles transcript delivery
  }, [onTranscript])

  const startRecording = useCallback(async () => {
    if (!apiKey || recording || disabled) return

    setError(null)

    try {
      const { SonioxClient } = await import('@soniox/speech-to-text-web')

      // Create a new client each time with callbacks
      clientRef.current = new SonioxClient({
        apiKey,
        onFinished: () => {
          // Deliver accumulated text when Soniox finishes
          const full = (finalTextRef.current + partialRef.current).trim()
          if (full) {
            onTranscript(full)
          }
          finalTextRef.current = ''
          partialRef.current = ''
        },
        onPartialResult: (result: any) => {
          const tokens = result?.tokens ?? []
          // Separate final (confirmed) tokens from non-final (partial) tokens
          const finalText = tokens.filter((t: any) => t.is_final).map((t: any) => t.text ?? '').join('')
          const nonFinalText = tokens.filter((t: any) => !t.is_final).map((t: any) => t.text ?? '').join('')

          if (finalText) {
            finalTextRef.current = finalText
          }
          partialRef.current = nonFinalText

          // Show full preview
          const preview = (finalTextRef.current + nonFinalText).trim()
          if (preview) {
            onPartial(preview)
          }
        },
        onError: (status: any, message: string) => {
          console.error('Soniox error:', status, message)
          setError('Transcription error')
          stopRecording()
        },
      })

      finalTextRef.current = ''
      partialRef.current = ''

      await clientRef.current.start({
        model: 'stt-rt-preview',
        languageHints: [language],
      })

      setRecording(true)
      setDuration(0)

      timerRef.current = setInterval(() => {
        setDuration(d => d + 1)
      }, 1000)
    } catch (err: any) {
      console.error('Recording start error:', err)
      if (err?.name === 'NotAllowedError') {
        setError('Microphone access denied')
      } else if (err?.name === 'NotFoundError') {
        setError('No microphone found')
      } else {
        setError('Could not start recording')
      }
      setRecording(false)
    }
  }, [apiKey, recording, disabled, language, onPartial, stopRecording])

  const toggleRecording = useCallback(() => {
    if (recording) {
      stopRecording()
    } else {
      startRecording()
    }
  }, [recording, startRecording, stopRecording])

  // Cleanup on unmount
  useEffect(() => {
    return () => {
      if (timerRef.current) clearInterval(timerRef.current)
      if (clientRef.current) {
        try { clientRef.current.cancel() } catch (_) { /* ignore */ }
      }
    }
  }, [])

  // Don't render if no API key or mic not available
  if (!keyChecked || !apiKey || !micAvailable) {
    return null
  }

  const formatDuration = (secs: number) => {
    const m = Math.floor(secs / 60)
    const s = secs % 60
    return `${m}:${s.toString().padStart(2, '0')}`
  }

  return (
    <div className="flex items-center gap-1">
      {/* Language selector */}
      <select
        value={language}
        onChange={e => setLanguage(e.target.value as Language)}
        disabled={recording || disabled}
        className="bg-neutral-800 text-neutral-300 text-sm rounded px-1 min-h-[44px] md:min-h-[32px] border border-neutral-700 focus:outline-none focus:border-blue-500 disabled:opacity-50"
      >
        <option value="hu">HU</option>
        <option value="en">EN</option>
      </select>

      {/* Mic button */}
      <button
        onClick={toggleRecording}
        disabled={disabled}
        title={recording ? 'Stop recording' : 'Start voice input'}
        className={`flex items-center justify-center min-w-[44px] min-h-[44px] rounded-lg transition-all ${
          recording
            ? 'bg-red-600 hover:bg-red-500 text-white animate-pulse'
            : 'bg-neutral-800 hover:bg-neutral-700 text-neutral-400 hover:text-neutral-200'
        } disabled:opacity-50 disabled:cursor-not-allowed`}
      >
        <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
          <path d="M12 1a3 3 0 0 0-3 3v8a3 3 0 0 0 6 0V4a3 3 0 0 0-3-3z" />
          <path d="M19 10v2a7 7 0 0 1-14 0v-2" />
          <line x1="12" y1="19" x2="12" y2="23" />
          <line x1="8" y1="23" x2="16" y2="23" />
        </svg>
      </button>

      {/* Duration display */}
      {recording && (
        <span className="text-sm text-red-400 min-w-[32px]">
          {formatDuration(duration)}
        </span>
      )}

      {/* Error display */}
      {error && (
        <span className="text-sm text-red-400" onClick={() => setError(null)}>
          {error}
        </span>
      )}
    </div>
  )
}
