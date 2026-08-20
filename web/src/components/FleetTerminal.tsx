import { useCallback, useEffect, useRef, useState } from 'react'
import { ChevronDown, ChevronRight, CircleStop, Eye, Maximize2, Minimize2, Scissors, X } from 'lucide-react'
import {
  type AttachedEvent,
  parseControl,
  terminalUrl,
} from '../lib/fleetTerminal'
import { IconButton } from './TileControls'

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

/**
 * The narrowest terminal worth handing to a program — see `refit` below.
 *
 * 80 because that is the width terminal programs assume when they assume one;
 * anything narrower is not a smaller terminal, it is a broken one.
 */
const MIN_COLS = 80

/**
 * How long to wait for a replay that never finishes arriving — B-16.
 *
 * The replay is normally one burst and this timer never fires. It exists for
 * the case where the byte count and what arrives disagree: without it the
 * viewer would keep the pty at the geometry it was found in and never send its
 * own, so a resize would silently stop working. One second is far longer than a
 * local burst and far shorter than a person noticing.
 */
const REPLAY_GRACE_MS = 1000

interface Props {
  label: string
  /** Called when the reader closes the view. Detach only — never a stop. */
  onClose: () => void
  /**
   * Whether this terminal's agent is alone on the panel. Only changes the
   * height — the socket, the replay and the pty are identical either way.
   */
  full?: boolean
  /** Ask the panel to show this agent alone, or to go back to the grid. */
  onToggleFull?: () => void
  /**
   * Called on every keystroke the reader sends into this terminal.
   *
   * Distinct from `onFocusChange`, and the distinction is the whole point:
   * focus says the cursor is here, which can be true for fifteen minutes while
   * nothing happens. PM mode's freeze has to know whether the reader is
   * ACTING, because a screen somebody is parked on with nothing typed is
   * exactly the one a fresher blockage may take.
   *
   * Fires for pasted and program-generated input too. That is correct rather
   * than sloppy — all of it is the reader putting something into this session.
   */
  onInput?: () => void
  /**
   * Called when the keyboard enters or leaves this terminal.
   *
   * Asked for on 2026-08-19: *"az aktuális csempe, amin gépelek, lehetne
   * aktívan jelezve"* — and with several terminals open at once (which is now
   * possible) it stops being decoration: a keystroke goes to exactly one agent,
   * and the reader has to be able to see which. It is taken from real DOM focus
   * on the emulator's own textarea, not from which pane was opened last — the
   * latter is a proxy, and it would say "here" while the keys went elsewhere.
   */
  onFocusChange?: (focused: boolean) => void
}

type Phase =
  | { kind: 'connecting' }
  | { kind: 'attached'; ack: AttachedEvent }
  | { kind: 'refused'; reason: string }
  | { kind: 'closed'; reason: string }

export default function FleetTerminal({ label, onClose, full, onToggleFull, onFocusChange, onInput }: Props) {
  const host = useRef<HTMLDivElement | null>(null)
  // Held in a ref because the effect below depends on `[label]` alone: the
  // handler is captured once, so a parent passing a fresh closure each render
  // would have its FIRST one called forever. That failure is silent — the
  // callback still fires, it just reports to a stale owner — which is exactly
  // the kind of thing a passing test suite does not notice.
  const onInputRef = useRef(onInput)
  onInputRef.current = onInput
  const [phase, setPhase] = useState<Phase>({ kind: 'connecting' })
  const [stopping, setStopping] = useState(false)
  const [stopError, setStopError] = useState<string | null>(null)
  const [stopConfirm, setStopConfirm] = useState(false)
  // The attachment details start CLOSED: they are the two facts nothing goes
  // wrong for lack of — the label is already in the tile's title, and the byte
  // count is a measurement of the replay, not of the agent.
  const [details, setDetails] = useState(false)

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

      /**
       * Fit to the box, but never below a usable width — B-13.
       *
       * `FitAddon` derives the column count from the container, and that number
       * goes on to the pty, so a narrow tile does not merely wrap the view: it
       * tells the AGENT to redraw its own terminal UI at that width. Measured at
       * ~30 columns the result is a third-width body with a one-character column
       * stranded at the right edge — *"hülyén tördel … nagyban jól működik"*.
       *
       * A terminal is a fixed-grid device: its content was laid out by the
       * program for a given number of columns, so re-flowing it destroys the
       * layout rather than adapting it. Hence a FLOOR and a window onto the
       * result — the host scrolls horizontally — instead of a cleverer wrap.
       * Above the floor nothing changes, which is why the large case already
       * worked.
       */
      const refit = () => {
        try { fit.fit() } catch { return /* zero-sized container; the observer refits */ }
        if (term.cols < MIN_COLS) term.resize(MIN_COLS, term.rows)
        /*
          B-29 — AND THEN CHECK THAT IT ACTUALLY FITS.

          `FitAddon` derives the row count from the host's OUTER box, so the 1 px
          border on each side is never subtracted. At heights that land just
          under a row multiple it therefore hands back one row MORE than fits,
          and `overflow-y: hidden` cuts the last one. Measured 2026-08-20: a
          224 px host has a 222 px client box, 16 rows x 14 px = 224, and the
          last row showed 12 of its 14 px.

          The row that gets cut is always the last one, which is where every
          terminal program draws its status line — so this is not "one row
          short", it is losing the row that says what the agent is waiting for,
          while everything above it still looks correct.

          The correction is measured against what was RENDERED, not recomputed
          from the box: the cell height is xterm's, and a second copy of that
          arithmetic here would be a second place to drift.
        */
        const el = host.current
        const screen = el?.querySelector('.xterm-screen') as HTMLElement | null
        if (!el || !screen || term.rows < 1) return
        const cell = screen.offsetHeight / term.rows
        if (!(cell > 0)) return
        const fits = Math.floor(el.clientHeight / cell)
        if (fits >= 1 && fits < term.rows) term.resize(term.cols, fits)
      }
      refit()

      const ws = new WebSocket(terminalUrl(label))
      ws.binaryType = 'arraybuffer'
      socket = ws
      const encoder = new TextEncoder()

      /** The pty's size, sent once the replay has landed and on every resize. */
      const sendSize = () => {
        if (ws.readyState !== WebSocket.OPEN) return
        ws.send(JSON.stringify({ resize: { rows: term.rows, cols: term.cols } }))
      }

      /*
        THE TWO GEOMETRIES, AND WHY THEY ARE SEQUENCED — B-16.

        The replay must render at the pty's shape; the tile must then get its
        own. Doing the second before the first has finished resizes the grid out
        from under the bytes, which is the bug this repairs, one layer down.

        `replayLeft` is counted down from `replayed_bytes` — an exact number the
        server sends BEFORE any byte — so the end of the replay is arithmetic,
        not a guess about timing. `settle` is idempotent and also fires on a
        timer, because a replay that arrives short (a dropped frame, a socket
        that ends mid-burst) must not leave the pty stuck at a size nobody is
        looking at. Failing towards "send our size late" is the safe direction;
        failing towards "never send it" is not.
      */
      let replayLeft = 0
      let settled = false
      let settleTimer: number | undefined
      const settle = () => {
        if (settled) return
        settled = true
        if (settleTimer !== undefined) { window.clearTimeout(settleTimer); settleTimer = undefined }
        refit()
        sendSize()
      }

      ws.onmessage = ev => {
        if (typeof ev.data === 'string') {
          const control = parseControl(ev.data)
          if (!control) return
          if (control.event === 'attached') {
            const ack = control as AttachedEvent
            setPhase({ kind: 'attached', ack })
            /*
              B-16 — RENDER THE REPLAY AT THE GEOMETRY IT WAS DRAWN AT.
              Reported 2026-08-19: *"terminal also status bar elromlik ha
              projektet valtok, beleirok, majd visszavaltok"*, and the half that
              names the cause: *"beiras utan megjavul"*. A keystroke changes
              nothing about the socket, the pty or the buffer — it makes the
              remote program REPAINT. So the screen was stale, not lost.

              This ack reaches the browser BEFORE any replay byte (the bridge
              sends it, then starts the output pump), which is what makes the
              repair possible here and nowhere else: adopt the pty's shape
              first, and the bytes that follow land on the grid they were
              composed for. Without it the viewer fitted to its own tile and
              rendered a screen laid out for some other width — silently,
              because the result still looks like a terminal.

              Then, and only then, our own size goes back. If it differs the
              program gets a SIGWINCH and repaints, which is the ordinary path;
              if it matches there is nothing to repaint and nothing is stale.
            */
            if (ack.rows && ack.cols) term.resize(ack.cols, ack.rows)
            // Our own size goes back only once the replay has landed — see
            // `settle` below. Sending it here would resize the grid out from
            // under the very bytes this is protecting.
            replayLeft = ack.replayed_bytes
            if (replayLeft <= 0) settle()
            else settleTimer = window.setTimeout(settle, REPLAY_GRACE_MS)
            term.focus()
            return
          }
          if (control.event === 'unavailable' || control.event === 'refused') {
            setPhase({ kind: 'refused', reason: String((control as { reason?: unknown }).reason ?? control.event) })
          }
          return
        }
        // Bytes, straight through. No decode: see the header of this file.
        const bytes = new Uint8Array(ev.data as ArrayBuffer)
        term.write(bytes)
        // The replay is counted DOWN, not detected. `replayed_bytes` is exact
        // and the server sends it before a single byte, so the end of the
        // replay is arithmetic rather than a guess about timing.
        if (replayLeft > 0) {
          replayLeft -= bytes.length
          if (replayLeft <= 0) settle()
        }
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
        onInputRef.current?.()
        if (ws.readyState === WebSocket.OPEN) ws.send(encoder.encode(data))
      })

      const observer = new ResizeObserver(() => {
        refit()
        sendSize()
      })
      observer.observe(host.current)

      // Focus is READ from the DOM rather than tracked by hand. `focusin` /
      // `focusout` bubble (unlike focus/blur), so one pair on the host covers
      // the emulator's textarea whatever it does internally.
      const el = host.current
      const gained = () => onFocusChange?.(true)
      const lost = () => onFocusChange?.(false)
      el.addEventListener('focusin', gained)
      el.addEventListener('focusout', lost)

      dispose = () => {
        if (settleTimer !== undefined) window.clearTimeout(settleTimer)
        observer.disconnect()
        el.removeEventListener('focusin', gained)
        el.removeEventListener('focusout', lost)
        // Leaving takes the keyboard with it: a tile left marked as typed-into
        // after its terminal is gone points at an agent that cannot receive a
        // keystroke.
        onFocusChange?.(false)
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
    // `label` only. Adding the callbacks here would tear down the socket and
    // re-attach every time the parent re-renders with a new closure — a reattach
    // storm that looks like a flickering terminal and costs a replay each time.
    // eslint-disable-next-line react-hooks/exhaustive-deps
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
    <div
      className="border-t border-surface-line mt-3 pt-2 flex-1 min-h-0 flex flex-col"
      data-fleet-terminal={label}
      data-fleet-own-surface="terminal"
    >
      {/*
        ONE row, and it does NOT wrap — asked for 2026-08-19: *"latszik hogy sok
        helyet elfoglal az agent felső menüsora még a terminal nezet előtt, ezt
        kompaktálni kell. 1 sor elég kellene legyen ikonokkal"*. It used to be
        two: `flex-wrap` plus an `ml-auto` control block meant the three
        sentences dropped onto a line of their own, so five rows stood between
        the tile's title and the terminal.

        ## What stays visible, and why it is not a style choice

        `ui-quality.md`: compaction must never hide a failure. So the split here
        is not text-vs-icon, it is **caveat vs detail**:

        - The PHASE always shows, in its own colour — `connecting…`, `live`,
          a refusal, a close reason. A terminal whose state is one disclosure
          away is a terminal that looks attached while it is not.
        - The two amber facts — a replay whose head was cut, and a second viewer
          who sees your keystrokes — stay as coloured icons. An alarm in a
          tooltip is not an alarm; it is something you have to already suspect.
        - Only the plain numbers move behind the toggle: the label and the byte
          count. Neither is wrong when unseen.
      */}
      <div className="flex items-center gap-1.5 mb-1.5 min-w-0">
        <span className="text-xs text-fg-strong shrink-0">terminal</span>

        {phase.kind === 'connecting' && (
          <span className="text-xs text-sky-400 shrink-0" data-fleet-terminal-phase="connecting">connecting…</span>
        )}
        {phase.kind === 'attached' && (
          <>
            <span className="text-xs text-emerald-400 shrink-0" data-fleet-terminal-phase="attached">live</span>
            {/* Rendered from the acknowledgement, not from a guess: a replay that
                quietly lost its head reads as a session that began there. The
                sentence is unchanged — it moved from the row into the icon's
                accessible name, so nothing that had to be SAID is now unsaid. */}
            {phase.ack.replay_truncated && (
              <IconButton
                icon={Scissors}
                tone="amber"
                testId="replay-truncated"
                mark={{ 'data-fleet-terminal-replay-truncated': 'yes' }}
                label="the start of the buffer was cut — this replay does not begin where the session began"
              />
            )}
            {phase.ack.viewers > 1 && (
              <IconButton
                icon={Eye}
                tone="amber"
                testId="viewers"
                mark={{ 'data-fleet-terminal-viewers': String(phase.ack.viewers) }}
                label={`${phase.ack.viewers} watching — somebody else is on this same terminal and sees what you type`}
              />
            )}
          </>
        )}
        {phase.kind === 'refused' && (
          <span className="text-xs text-red-400 truncate" data-fleet-terminal-phase="refused">
            did not open: {phase.reason}
          </span>
        )}
        {phase.kind === 'closed' && (
          <span className="text-xs text-amber-400 truncate" data-fleet-terminal-phase="closed">{phase.reason}</span>
        )}

        {/* The details, on request — *"esetleg lenyitható részletekkel"*. */}
        <IconButton
          icon={details ? ChevronDown : ChevronRight}
          testId="details"
          active={details}
          label={details ? 'hide the attachment details' : 'the terminal label and how much screen was replayed'}
          onClick={() => setDetails(d => !d)}
        />

        <span className="ml-auto flex items-center gap-0.5 shrink-0">
          {/* Two controls, never one. Requirement 5.4: closing the view is not a
              stop, so the stop has to be its own act — and it still says so, in
              the accessible name that replaced the sentence. The confirm step is
              what an icon on its own could not carry, so it is kept: the first
              click arms, the second acts. */}
          {stopConfirm ? (
            <IconButton
              icon={CircleStop}
              tone="amber"
              testId="stop-confirm"
              active
              mark={{ 'data-fleet-terminal-stop-confirm': 'armed' }}
              label={stopping ? 'stopping…' : 'sure? stop it — the process ends, which is not the same as closing this view'}
              onClick={() => { if (!stopping) void stop() }}
            />
          ) : (
            <IconButton
              icon={CircleStop}
              testId="stop"
              mark={{ 'data-fleet-terminal-stop': 'armable' }}
              label="stop the agent — a separate, explicit act"
              onClick={() => setStopConfirm(true)}
            />
          )}
          {onToggleFull && (
            <IconButton
              icon={full ? Minimize2 : Maximize2}
              testId="full"
              active={full}
              mark={{ 'data-fleet-terminal-full': full ? 'on' : 'off' }}
              label={full
                ? 'back to the grid — the terminal stays attached, nothing is stopped or reconnected'
                : 'show this agent alone, filling the panel — the other agents are counted in the header, not silently dropped'}
              onClick={onToggleFull}
            />
          )}
          <IconButton
            icon={X}
            testId="close"
            mark={{ 'data-fleet-terminal-close': 'yes' }}
            label="close (the agent keeps running) — detach only, and you can attach here again later"
            onClick={onClose}
          />
        </span>
      </div>

      {details && (
        <div className="text-xs text-fg-ghost mb-1.5 flex items-baseline gap-2 flex-wrap" data-fleet-terminal-details>
          <span className="truncate max-w-[24rem]">{label}</span>
          {phase.kind === 'attached' && (
            <span className="tabular-nums" title="How much of the screen was replayed when this view attached.">
              {phase.ack.replayed_bytes} bytes replayed
            </span>
          )}
        </div>
      )}

      {stopError && (
        <div className="text-xs text-red-400 mb-1">the stop failed: {stopError}</div>
      )}

      <div
        ref={host}
        data-fleet-terminal-host
        /* Full screen fills what the card gives it, rather than taking a guessed
           fraction of the viewport. `62vh` was that guess, and it is why the
           maximised agent stopped ~100 px short of the bottom — raised
           2026-08-19: *"agent maximize nem nyitja ki teljesen az aljáig"*. No
           single fraction can be right: the strip above this varies with the
           header, the waiters and the modules panel, so the only correct height
           is the one that is left. The `ResizeObserver` above refits xterm, so a
           flexible box is not a problem for the terminal itself. */
        /* `flex-[1_1_12rem] min-h-0`, and the two halves are one decision — B-29.
           12rem used to be a `min-height`, i.e. a floor nothing could take back.
           In the grid that is right: the card is content-sized and the floor is
           what gives the terminal its size at all. In the enlarged card it is
           not: that card is a `flex-1` child of a chain that ends in
           `overflow: hidden`, so a floor larger than the room left does not make
           the terminal bigger, it pushes its bottom out of the card — measured
           2026-08-20 at a 440 px window, last row 4 of 14 px, and at 400 px gone
           entirely with the page unable to scroll to it.

           As a flex BASIS the same 12rem is a preference: it still contributes
           192 px to a content-sized card, and it yields when there is less room
           rather than overflowing. The alternative — letting the card scroll —
           was rejected: it keeps the floor and puts the status line below a fold
           the reader has to discover, which is the shape `ui-quality.md`
           forbids. A short terminal is honest; a truncated one is not. */
        className="flex-[1_1_12rem] min-h-0 rounded border border-surface-edge overflow-x-auto overflow-y-hidden bg-[#0b0f14]"
      />
    </div>
  )
}
