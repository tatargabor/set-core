import { useCallback, useEffect, useRef, useState } from 'react'
import {
  type AttachedEvent,
  parseControl,
  terminalUrl,
} from '../lib/fleetTerminal'

/**
 * One framework-owned terminal, in the browser — task 8.1.
 *
 * ## The wire, and why the split is not an implementation detail
 *
 * Terminal bytes travel as BINARY frames in both directions; control travels as
 * JSON text. A pty read can end in the middle of a UTF-8 sequence — that is
 * ordinary, not an edge case — so decoding at this boundary would corrupt output
 * silently and in the direction that still looks like data. The bytes therefore
 * go to the emulator **as bytes**: `term.write(Uint8Array)`, never
 * `term.write(new TextDecoder().decode(...))`. Keystrokes go back the same way,
 * encoded once and sent as binary.
 *
 * ## Closing this view does not stop the agent
 *
 * Requirement 5.4, and it is the reason there are two controls here rather than
 * one. `bezárás` detaches the socket; the owner keeps holding the pty and the
 * agent keeps working. Stopping is a separate, explicit act — `POST
 * /api/fleet/agents/{label}/stop` — and it says what it does before it does it.
 * A single ✕ that did both would make every reader who wanted to stop watching
 * kill the thing they were watching.
 *
 * ## Reattach is the ordinary case, not recovery
 *
 * The server sends the buffered screen first, so a reload, a second viewer and a
 * first attach are the same code path — the first frame is the screen as it
 * already is. `replayed_bytes` says how much came back, and `replay_truncated`
 * says the buffer was longer than what was kept. Both are rendered: a replay
 * that silently lost its head would otherwise read as a session that started
 * there.
 *
 * ## Why xterm is loaded dynamically
 *
 * `import()` inside the effect rather than at module scope. Two reasons, both
 * measured rather than stylistic: the emulator is ~300 KB that no reader who
 * never opens a terminal should download, and a static import would drag a
 * canvas/DOM-heavy module into every jsdom unit test that renders an agent tile.
 */

interface Props {
  label: string
  /** Called when the reader closes the view. Detach only — never a stop. */
  onClose: () => void
}

type Phase =
  | { kind: 'connecting' }
  | { kind: 'attached'; ack: AttachedEvent }
  | { kind: 'refused'; reason: string }
  | { kind: 'closed'; reason: string }

export default function FleetTerminal({ label, onClose }: Props) {
  const host = useRef<HTMLDivElement | null>(null)
  const [phase, setPhase] = useState<Phase>({ kind: 'connecting' })
  const [stopping, setStopping] = useState(false)
  const [stopError, setStopError] = useState<string | null>(null)
  const [stopConfirm, setStopConfirm] = useState(false)

  useEffect(() => {
    let disposed = false
    let socket: WebSocket | null = null
    let dispose: (() => void) | null = null

    void (async () => {
      const [{ Terminal }, { FitAddon }] = await Promise.all([
        import('@xterm/xterm'),
        import('@xterm/addon-fit'),
      ])
      await import('@xterm/xterm/css/xterm.css')
      if (disposed || !host.current) return

      const term = new Terminal({
        convertEol: false,
        cursorBlink: true,
        fontSize: 12,
        fontFamily: 'ui-monospace, SFMono-Regular, Menlo, monospace',
        scrollback: 5000,
        theme: { background: '#0b0f14', foreground: '#d7dde4' },
      })
      const fit = new FitAddon()
      term.loadAddon(fit)
      term.open(host.current)
      try { fit.fit() } catch { /* zero-sized container; the observer refits */ }

      const ws = new WebSocket(terminalUrl(label))
      ws.binaryType = 'arraybuffer'
      socket = ws
      const encoder = new TextEncoder()

      /** The pty's size, sent once attached and on every resize afterwards. */
      const sendSize = () => {
        if (ws.readyState !== WebSocket.OPEN) return
        ws.send(JSON.stringify({ resize: { rows: term.rows, cols: term.cols } }))
      }

      ws.onmessage = ev => {
        if (typeof ev.data === 'string') {
          const control = parseControl(ev.data)
          if (!control) return
          if (control.event === 'attached') {
            setPhase({ kind: 'attached', ack: control as AttachedEvent })
            sendSize()
            term.focus()
            return
          }
          if (control.event === 'unavailable' || control.event === 'refused') {
            setPhase({ kind: 'refused', reason: String((control as { reason?: unknown }).reason ?? control.event) })
          }
          return
        }
        // Bytes, straight through. No decode: see the header of this file.
        term.write(new Uint8Array(ev.data as ArrayBuffer))
      }
      ws.onerror = () => {
        setPhase(p => (p.kind === 'attached' ? p : { kind: 'refused', reason: 'the connection was not established' }))
      }
      ws.onclose = () => {
        setPhase(p => (
          p.kind === 'refused'
            ? p
            : { kind: 'closed', reason: 'the connection closed — the agent may still be running' }
        ))
      }

      const typed = term.onData(data => {
        if (ws.readyState === WebSocket.OPEN) ws.send(encoder.encode(data))
      })

      const observer = new ResizeObserver(() => {
        try { fit.fit() } catch { /* detached mid-teardown */ }
        sendSize()
      })
      observer.observe(host.current)

      dispose = () => {
        observer.disconnect()
        typed.dispose()
        term.dispose()
      }
      if (disposed) { dispose(); ws.close() }
    })()

    return () => {
      disposed = true
      dispose?.()
      // Detach. The owner keeps the pty; requirement 5.4 makes this explicitly
      // not a stop, so nothing here touches the agent's lifetime.
      socket?.close()
    }
  }, [label])

  const stop = useCallback(async () => {
    setStopping(true)
    setStopError(null)
    try {
      const res = await fetch(`/api/fleet/agents/${encodeURIComponent(label)}/stop`, { method: 'POST' })
      if (!res.ok) {
        const body = await res.json().catch(() => null)
        setStopError(String(body?.detail ?? `HTTP ${res.status}`))
        return
      }
      onClose()
    } catch (e) {
      setStopError(String((e as Error)?.message ?? e))
    } finally {
      setStopping(false)
      setStopConfirm(false)
    }
  }, [label, onClose])

  return (
    <div className="border-t border-surface-line mt-3 pt-2" data-fleet-terminal={label}>
      <div className="flex items-baseline gap-2 flex-wrap mb-1.5">
        <span className="text-xs text-fg-strong">terminal</span>
        <span className="text-xs text-fg-ghost truncate max-w-[16rem]">{label}</span>

        {phase.kind === 'connecting' && (
          <span className="text-xs text-sky-400" data-fleet-terminal-phase="connecting">connecting…</span>
        )}
        {phase.kind === 'attached' && (
          <>
            <span className="text-xs text-emerald-400" data-fleet-terminal-phase="attached">live</span>
            {/* Rendered from the acknowledgement, not from a guess: a replay that
                quietly lost its head reads as a session that began there. */}
            <span className="text-xs text-fg-ghost tabular-nums" title="How much of the screen was replayed when this view attached.">
              {phase.ack.replayed_bytes} bytes replayed
              {phase.ack.replay_truncated && (
                <span className="text-amber-400"> · the start of the buffer was cut</span>
              )}
            </span>
            {phase.ack.viewers > 1 && (
              <span className="text-xs text-amber-400 tabular-nums" title="Somebody else is watching this same terminal — they see what you type.">
                {phase.ack.viewers} watching
              </span>
            )}
          </>
        )}
        {phase.kind === 'refused' && (
          <span className="text-xs text-red-400" data-fleet-terminal-phase="refused">
            did not open: {phase.reason}
          </span>
        )}
        {phase.kind === 'closed' && (
          <span className="text-xs text-amber-400" data-fleet-terminal-phase="closed">{phase.reason}</span>
        )}

        <div className="ml-auto flex items-baseline gap-2">
          {/* Two controls, never one. Requirement 5.4: closing the view is not a
              stop, so the stop has to be its own act — and it says so. */}
          {stopConfirm ? (
            <button
              onClick={() => void stop()}
              disabled={stopping}
              data-fleet-terminal-stop-confirm
              className="text-xs text-red-400 hover:text-red-300 disabled:opacity-50"
              title="The process stops. This is not the same as closing the view."
            >
              {stopping ? 'stopping…' : 'sure? stop it'}
            </button>
          ) : (
            <button
              onClick={() => setStopConfirm(true)}
              data-fleet-terminal-stop
              className="text-xs text-fg-muted hover:text-red-400"
              title="Stop the agent — a separate, explicit act"
            >
              stop the agent
            </button>
          )}
          <button
            onClick={onClose}
            data-fleet-terminal-close
            className="text-xs text-fg-muted hover:text-fg-strong"
            title="Detach only. The agent keeps running and you can attach here again later."
          >
            close (the agent keeps running)
          </button>
        </div>
      </div>

      {stopError && (
        <div className="text-xs text-red-400 mb-1">the stop failed: {stopError}</div>
      )}

      <div
        ref={host}
        data-fleet-terminal-host
        className="h-72 rounded border border-surface-line overflow-hidden bg-[#0b0f14]"
      />
    </div>
  )
}
