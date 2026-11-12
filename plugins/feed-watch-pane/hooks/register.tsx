// feed-watch-pane: at the user's chosen times, a pane asks whether to run this project's
// feed-watch skill now, in an hour, tomorrow, or never again. Inert unless the CURRENT Claude
// account opted in for THIS project (`set-feed-watch optin on`) and the project declares
// `.set/feed-watch.yaml`.
import { read, update } from 'claude-code'
import type { EngineInterface, Register } from 'claude-code'

import type { FwPrompt } from '../types'
import {
  accountEmail,
  answer,
  disabled,
  dueSlot,
  heldByOther,
  isActive,
  parseEntry,
  parseState,
  slotLabel,
  withState,
  type Answer,
  type Entry,
} from './logic'

const PANE = 'feed-watch'
const TICK_MS = 60_000
const DECLARATION = '.set/feed-watch.yaml'
const prompt = { plugin: 'feed-watch-pane', key: 'prompt' } as const
const instance = { plugin: 'feed-watch-pane', key: 'instance' } as const

type Paths = { optin: string; state: string; claudeJson: string }

/** Mirrors set_orch.local_config.config_dir(): SET_CONFIG_DIR, then XDG_CONFIG_HOME, then ~/.config. */
async function pathsOf($: EngineInterface): Promise<Paths | null> {
  const home = await $.env.get('HOME')
  if (!home) return null
  const override = await $.env.get('SET_CONFIG_DIR')
  const xdg = await $.env.get('XDG_CONFIG_HOME')
  const ccDir = await $.env.get('CLAUDE_CONFIG_DIR')
  const dir = override || `${xdg || `${home}/.config`}/set-core`
  return {
    optin: `${dir}/feed-watch.json`,
    state: `${dir}/feed-watch.state.json`,
    claudeJson: ccDir ? `${ccDir}/.claude.json` : `${home}/.claude.json`,
  }
}

const readOr = async ($: EngineInterface, path: string): Promise<string | undefined> =>
  $.fs.read(path).then(t => (typeof t === 'string' ? t : undefined)).catch(() => undefined)

/** Local date and time from the host clock (the module's own Date may not know the zone). */
async function localNow($: EngineInterface): Promise<{ date: string; hhmm: string }> {
  const r = await $.process.run(['date', '+%Y-%m-%d %H:%M']).catch(() => null)
  const m = r?.stdout.trim().match(/^(\d{4}-\d{2}-\d{2}) (\d{2}:\d{2})$/)
  if (m?.[1] && m[2]) return { date: m[1], hhmm: m[2] }
  const d = new Date(await $.clock.now())
  const p = (n: number) => String(n).padStart(2, '0')
  return { date: `${d.getFullYear()}-${p(d.getMonth() + 1)}-${p(d.getDate())}`, hhmm: `${p(d.getHours())}:${p(d.getMinutes())}` }
}

/** The project root, when this session runs in a project that declares feed-watch. */
async function projectRoot($: EngineInterface): Promise<string | null> {
  const r = await $.process.run(['git', 'rev-parse', '--show-toplevel']).catch(() => null)
  const root = r && r.exitCode === 0 ? r.stdout.trim() : ''
  if (!root) return null
  return (await $.fs.exists(`${root}/${DECLARATION}`)) ? root : null
}

async function activeEntry($: EngineInterface, p: Paths, root: string): Promise<Entry | null> {
  const e = parseEntry(await readOr($, p.optin), root)
  const email = accountEmail(await readOr($, p.claudeJson))
  return isActive(e, email) ? e : null
}

async function myId($: EngineInterface): Promise<string> {
  const held = await read($, instance)
  if (held) return held
  const id = Math.random().toString(36).slice(2, 10)
  await update($, instance, () => id)
  return id
}

async function tick($: EngineInterface): Promise<void> {
  const p = await pathsOf($)
  if (!p) return
  const shown = await read($, prompt)
  const root = await projectRoot($)
  const entry = root ? await activeEntry($, p, root) : null
  if (!root || !entry) {
    if (shown) await close($)
    return
  }
  const stText = await readOr($, p.state)
  const st = parseState(stText, root)
  const now = await $.clock.now()
  const { date, hhmm } = await localNow($)
  const slot = dueSlot(date, hhmm, entry.times, st, now)
  const me = await myId($)

  if (!slot || heldByOther(st, slot, me, now)) {
    // answered in another session, snoozed, or the slot passed: take our pane down
    if (shown) await close($)
    return
  }
  if (shown?.slot === slot) return

  await $.fs.write(p.state, withState(stText, root, { ...st, shown: { slot, by: me, at: now } }))
  await update($, prompt, () => ({ slot, label: slotLabel(slot) }))
  const opened = await $.ui.open({ id: PANE, title: 'feed-watch', focus: true, rows: 9 })
  $.ui.status('feed-watch: a collection run is due')
  if (!opened.isPlaced) {
    $.ui.toast('feed-watch: a collection run is due. The pane appears in a wider window, or type /feed-watch-pane now', {
      timeoutMs: 15_000,
    })
  }
}

async function close($: EngineInterface): Promise<void> {
  await update($, prompt, () => null)
  $.ui.status(undefined)
  await $.ui.close({ id: PANE }).catch(() => undefined)
}

async function respond($: EngineInterface, a: Answer | 'off'): Promise<void> {
  const p = await pathsOf($)
  const root = await projectRoot($)
  const shown = await read($, prompt)
  if (!p || !root) return
  const now = await $.clock.now()
  if (a === 'off') {
    await $.fs.write(p.optin, disabled(await readOr($, p.optin), root))
    $.ui.toast('feed-watch pane switched off for this project. To switch it back on: set-feed-watch optin on')
  } else if (shown) {
    const stText = await readOr($, p.state)
    await $.fs.write(p.state, withState(stText, root, answer(parseState(stText, root), shown.slot, a, now)))
    if (a === 'snooze') $.ui.toast('feed-watch: I will ask again in an hour.')
    if (a === 'tomorrow') $.ui.toast('feed-watch: no more asking today.')
  }
  await close($)
  if (a === 'run') await runSkill($)
}

/** A LOCAL run in this session: collection needs the user's own Chrome. */
async function runSkill($: EngineInterface): Promise<void> {
  const ran = await $.command
    .run({ command: 'feed-watch' })
    .then(() => true)
    .catch(() => false)
  if (!ran) {
    await $.prompt.submit({
      text: 'Run the feed-watch skill (.claude/skills/feed-watch/SKILL.md): collect, score, drafts, digest.',
    })
  }
}

export const register: Register = on => {
  on('session.start', async ($, e, next) => {
    const started = await next(e)
    await $.command.register({
      name: 'feed-watch-pane',
      description: 'feed-watch pane: now | status | off',
      argumentHint: 'now | status | off',
    })
    void tick($)
    $.clock.every(TICK_MS, () => void tick($))
    return started
  })

  on('command.run', { command: 'feed-watch-pane' }, async ($, e) => {
    const arg = e.args.trim()
    const p = await pathsOf($)
    if (!p) return { text: 'HOME is not set; the pane cannot work.' }
    const root = await projectRoot($)
    if (!root) return { text: `This project does not declare feed-watch (${DECLARATION} not found).` }
    const entry = parseEntry(await readOr($, p.optin), root)
    const email = accountEmail(await readOr($, p.claudeJson))
    if (arg === 'off') {
      await respond($, 'off')
      return { text: 'feed-watch pane switched off for this project.' }
    }
    if (arg === 'now') {
      if (!isActive(entry, email)) return { text: 'The pane is not switched on for this account here: set-feed-watch optin on' }
      const { date, hhmm } = await localNow($)
      await update($, prompt, () => ({ slot: `${date} ${hhmm}`, label: `manual (${hhmm})` }))
      await $.ui.open({ id: PANE, title: 'feed-watch', focus: true, rows: 9 })
      return { text: 'feed-watch pane opened.' }
    }
    const state = parseState(await readOr($, p.state), root)
    return {
      text: [
        `Project: ${root}`,
        `On for this account: ${isActive(entry, email) ? 'yes' : 'no'}`,
        `Times: ${(entry?.times ?? []).join(', ') || '-'}`,
        `/feed-watch available as a command: ${(await $.command.list()).some(c => c.name === 'feed-watch') ? 'yes' : 'no'}`,
        `State: ${JSON.stringify(state)}`,
      ].join('\n'),
    }
  })

  on('ui.render', { component: 'Pane', requestId: PANE }, async ($, e) => {
    const { Box, Text, Button } = $.ui.resolve(e)
    const shown: FwPrompt = (await read($, prompt)) ?? null
    if (!shown) {
      return (
        <Box flexDirection="column">
          <Text dimColor>No feed-watch run is due.</Text>
        </Box>
      )
    }
    return (
      <Box flexDirection="column">
        <Text bold>feed-watch: {shown.label} collection</Text>
        <Text dimColor>Bring the Chrome window to the front (logged in to the source) before you start.</Text>
        <Box flexDirection="row">
          <Button key="run" label="Run now" hotkey="1" variant="primary" onPress={() => respond($, 'run')} />
          <Button key="snooze" label="In 1 hour" hotkey="2" onPress={() => respond($, 'snooze')} />
          <Button key="tomorrow" label="Tomorrow" hotkey="3" onPress={() => respond($, 'tomorrow')} />
          <Button key="off" label="Switch off" hotkey="4" onPress={() => respond($, 'off')} />
        </Box>
      </Box>
    )
  })
}
