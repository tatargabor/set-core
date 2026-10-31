/**
 * The Now card's own text, in the languages it has a dictionary for (fleet-now-card 7.9).
 *
 * English is the product's language, the default, and the source of truth: every key is
 * defined in `en` first. `hu` is an extra dictionary the owner switches on with the local
 * setting `now.locale = hu` (`set-config set now.locale hu`); the server hands the value to
 * the page in both payloads. The setting lives in local config, never in the repository.
 *
 * What is translated: the card's chrome (tabs, counters, buttons, overlays, the help
 * legend, aria-labels and titles) and the strings the framework itself generates (markers,
 * empty states, default feedback). What is NEVER translated: anything the publisher wrote —
 * item sentences, why, option labels, outcomes, goal titles, advice, check evidence, refusal
 * reasons. That text already arrives in its own language.
 *
 * The window title (`Now · SET`) is not here on purpose: `bin/set-now` finds the window by it.
 *
 * Shape: a message is a string with `{name}` placeholders, or — where English inflects for a
 * count — `{ one, other }`, chosen by the `n` parameter. The Hungarian dictionary lives in
 * `nowI18n.hu.ts`, the one file the English-only UI check exempts by exact path.
 */

import { hu } from './nowI18n.hu'

export type Locale = 'en' | 'hu'
export const LOCALES: readonly Locale[] = ['en', 'hu']

export type Msg = string | { one: string; other: string }
export type Params = Record<string, string | number>

const en = {
  // ------------------------------------------------------------------ durations, clock
  // `ago.*` is only ever used inside an "… ago" sentence (marker.stale, goals.stale), so a
  // language whose "ago" is a suffix ("5 órája") can carry it here and drop it from those.
  'ago.min': '{n} min',
  'ago.h': '{n} h',
  'clock.yesterday': 'yesterday {time}',
  'time.recommended': 'recommended {time}',
  'time.ranked': 'ranked {time}',

  // ------------------------------------------------------------------ markers
  'marker.unreadable': { one: '{n} source could not be read: {list}', other: '{n} sources could not be read: {list}' },
  'marker.notSetUp': 'not set up: {list}',
  'marker.noPublisher': 'No ranked queue is published',
  'marker.noActions': 'The publisher accepts no actions',
  'marker.publisherUnread': 'Publisher could not read: {list}',
  'marker.partial': 'Queue is partial',
  'marker.stale': 'ranked {age} ago',
  'marker.malformed': '{n} item(s) unreadable, skipped',
  'marker.slowed': 'cues slowed',
  'marker.warnTitle': 'Something the card could not read or trust — what you see may be incomplete',
  'marker.infoTitle': 'A known gap, not an error: this source is not set up yet',
  'marker.loadError': 'Card could not load: {error}',

  // ------------------------------------------------------------------ empty state
  'empty.mutedOnly': 'Nothing in the switched-on tags — {n} hidden by switched-off ones.',
  'empty.calm': 'Nothing is waiting.',
  'empty.unknown': { one: 'Nothing to show — but {n} source could not be read.', other: 'Nothing to show — but {n} sources could not be read.' },
  'empty.closedToday': '{n} closed today.',

  // ------------------------------------------------------------------ feedback defaults
  'outcome.answer': 'Answer delivered',
  'outcome.done': 'Marked done',
  'outcome.delegate': 'Handed off',
  'outcome.later': 'Snoozed',
  'outcome.park-idea': 'Idea parked',
  'outcome.resume-note': 'Note kept',
  'outcome.wind-down-handoff': 'Handed off for tonight',
  'outcome.recheck': 'Check started',
  'outcome.fallback': 'Done',
  'outcome.notDelivered': 'Not delivered — the item stays.',
  'feedback.closedToday': ' · {n} closed today',
  'feedback.openFailed': 'Could not open {path}: {detail}',

  // ------------------------------------------------------------------ check
  'check.running': 'Checking whether it is still current…',
  'check.since': ' (since {time})',
  'check.stands': 'Still current — checked',
  'check.rewritten': 'Reworded after a check',
  'check.stale': 'No longer current — checked',
  'check.failed': 'The check did not finish',
  'check.button': 'Still current?',
  'check.buttonTitle': 'Check in the background whether this is still current — sent mail, inbox, commits, the project\'s notes. Reused for 2 hours; a daily limit applies.',
  'check.close': 'Close it — not needed',
  'times.title': 'When this was first recommended, and when the list was last ranked (and every item re-checked)',

  // ------------------------------------------------------------------ later
  'later.15m': '15 min',
  'later.1h': '1 h',
  'later.2h': '2 h',
  'later.4h': '4 h',
  'later.tomorrow': 'Tomorrow',
  'later.prompt': 'Bring it back in…',

  // ------------------------------------------------------------------ header
  'header.view': 'View',
  'tab.now': 'Now',
  'tab.nowTitle': 'The next card: one thing to do now',
  'tab.nowFailTitle': 'The next card — something on it could not be read',
  'tab.nowFail': 'Something on the card could not be read',
  'tab.goals': 'Goals',
  'tab.goalsTitle': 'The goals the work serves',
  'tab.goalsProposedTitle': { one: '{n} proposed goal awaits your verdict', other: '{n} proposed goals await your verdict' },
  'tab.goalsFail': 'The goals could not be read',
  'header.closed': ' closed',
  'header.closedTitle': 'Cards you closed today (Done, an answer, or Delegate)',
  'header.parked': ' parked',
  'header.parkedTitle': 'Ideas you parked instead of starting them',
  'header.focus': ' focus',
  'header.focusLabel': 'Today\'s focus projects',
  'header.focusTitle': 'Today\'s focus projects — pick up to three; cards from other projects wait unless a deadline is near',
  'header.park': ' Park',
  'header.parkLabel': 'Park an idea',
  'header.parkTitle': 'Park a new idea: it is written down and waits, instead of starting work now',
  'header.soundOn': ' Sound on',
  'header.soundOff': ' Sound off',
  'header.soundOnTitle': 'Cues will play',
  'header.soundOffTitle': 'Click anywhere to enable cue sounds',
  'header.help': 'Help',
  'header.helpTitle': 'What is what on this card',
  'header.pages': 'Project pages',
  'header.pagesTitle': "The projects' own pages",
  'header.pagesDownTitle': "The projects' own pages — {n} not answering",
  'pages.title': "Projects' own pages",
  'pages.loading': 'Checking…',
  'pages.none': 'No project declares a page yet.',
  'pages.failed': 'The page list could not be read: {detail}',
  'pages.up': 'Answering',
  'pages.down': 'Not answering ({detail})',
  'pages.downShort': 'not answering',
  'pages.malformed': '{n} declared page(s) skipped as malformed',
  'pages.howto': 'A project declares a page in its .set-endpoint.json ("pages": [{"name", "url"}]), or on this machine: set-config set pages \'[…]\' --project <name>.',
  'pages.refresh': 'Check again',

  // ------------------------------------------------------------------ the card
  'loading': 'Loading…',
  'windDown.past': 'It is past {hour}:00.',
  'windDown.tomorrow': 'Write tomorrow\'s first card',
  'windDown.handOff': 'Hand off {n} delegable',
  'windDown.park': 'Park projects with notes',
  'windDown.showQueue': 'Show the queue',
  'card.fromLastNight': 'From last night: {note}',
  'card.resume': 'Resume: {note}',
  'card.optionTitle': 'Answer with this — it goes back to where the question came from',
  'card.answerPlaceholder': '…or type your answer (Enter sends and closes)',
  'card.answerLabel': 'Answer',
  'card.sendLabel': 'Send answer',
  'card.sendTitle': 'Send the answer and close',
  'card.done': 'Done',
  'card.doneTitle': 'It is done — close the card; it will not come back',
  'card.goThere': 'Go there',
  'card.goThereTitle': 'Open where this came from — the agent, the project or the message',
  'card.notNeeded': 'Not needed…',
  'card.notNeededTitle': 'Not needed (any more) — say why in one line; the card closes and the ranker learns from the reason',
  'card.later': 'Later',
  'card.laterTitle': 'Not now — bring it back later; nothing is sent',
  'card.inProgress': 'Working on it',
  'card.inProgressTitle': "I'm on it now — not done: hide it and bring it back with my note",
  'inProgress.prompt': 'Working on it — when should it come back?',
  'inProgress.notePlaceholder': 'Where are you with it? (optional)',
  'inProgress.noteLabel': 'Progress note',
  'card.delegate': 'Delegate',
  'card.delegateTitle': 'Hand it to a colleague',
  'card.more': '{n} more',
  'card.nothingAfter': 'Nothing else after this',
  'card.heldBack': '{n} held back outside today\'s focus',
  'card.mutedHidden': '{n} hidden by switched-off tags',
  'meta.estimate': '~{n} min',
  'meta.due': 'due {date}',
  'meta.unblocks': 'unblocks {what}',
  'meta.waiting': 'waiting {age}',

  // ------------------------------------------------------------------ overlays
  'overlay.close': 'Close',
  'overlay.dismiss': 'Dismiss',
  'reasons.prompt': 'Could a colleague take this? Why keep it — one or two reasons.',
  'reasons.first': 'Reason',
  'reasons.second': 'Second reason (optional)',
  'reasons.secondLabel': 'Second reason',
  'reasons.keep': 'Keep it',
  'reasons.delegate': 'Delegate instead',
  'notNeeded.prompt': 'Why is it not needed? One line — the ranker reads it.',
  'notNeeded.label': 'Why not needed',
  'notNeeded.placeholder': 'e.g. we moved the domain elsewhere',
  'notNeeded.close': 'Close it',
  'idea.prompt': 'Park an idea — it will wait, not start.',
  'idea.label': 'Idea',
  'idea.park': 'Park it',
  'tomorrow.prompt': 'Tomorrow\'s first card',
  'tomorrow.save': 'Save',

  // ------------------------------------------------------------------ focus picker
  'focus.swap': '{max} focus projects already — swap out which one for {project}?',
  'focus.keepAsIs': 'Keep as is',
  'focus.notesPrompt': 'Where to pick it up again? One line each.',
  'focus.notePlaceholder': '{project} — next step',
  'focus.noteLabel': 'Resume note for {project}',
  'focus.save': 'Save focus',
  'focus.title': 'Today\'s focus — up to {max}',
  'focus.none': 'No project has an item right now.',
  'focus.notSaved': 'not saved',
  'focus.searchPlaceholder': 'Another project — type its name…',
  'focus.searchLabel': 'Find another project for today\'s focus',
  'focus.noMatch': 'No registered project matches "{query}".',
  'focus.saved': 'Focus saved.',
  'focus.notSent': 'Focus saved here, but the publisher did not get it: {reason}',

  // ------------------------------------------------------------------ tag strip
  'tags.allOn': 'all on',
  'tags.allOnTitle': 'Switch every tag back on',
  'tags.offTitle': '{name}: switched off — its cards do not come up. Click to switch on.',
  'tags.onTitle': '{name}: {n} card(s). Click to switch off.',

  // ------------------------------------------------------------------ help legend
  'help.title': 'What is what',
  'help.card': 'The card',
  'help.card.text': 'one thing to do next: the project, what to do, and why it is first.',
  'help.options': 'Blue buttons',
  'help.options.text': 'ready answers. One tap sends it back to where the question came from.',
  'help.text': 'Text field',
  'help.text.text': 'your own answer when no button fits. Enter or the arrow sends it, and an answer CLOSES the card — for "I\'m on it" use Working on it.',
  'help.goThere': 'Go there',
  'help.goThere.text': 'opens where the work is done: the agent in Fleet, or a link the card carries. Absent when there is no such place.',
  'help.done': 'Done',
  'help.done.text': 'it is finished; the card closes and will not come back.',
  'help.notNeeded': 'Not needed…',
  'help.notNeeded.text': 'it is moot (e.g. already handled, cancelled, moved) — write why in one line; it closes and the ranker learns from it.',
  'help.later': 'Later',
  'help.later.text': 'not now; pick when it should return. Nothing is sent anywhere.',
  'help.inProgress': 'Working on it',
  'help.inProgress.text': 'you are on it, it is not done: the card hides until the time you pick and comes back with your note. Nothing closes.',
  'help.delegate': 'Delegate',
  'help.delegate.text': 'hand it to a colleague (shown only when someone else could do it).',
  'help.times': 'recommended · ranked',
  'help.times.text': 'exact times: when this card was first recommended, and when the list was last ranked (every ranking also re-checks each card).',
  'help.check': 'Still current?',
  'help.check.text': 'checks this one card in the background — sent mail, inbox, commits, the project\'s notes — and rewords it or says it is no longer current. A result is reused for 2 hours; a daily limit applies.',
  'help.more': 'N more',
  'help.more.text': 'how many cards follow; you only ever see one.',
  'help.closed': '✓ closed',
  'help.closed.text': 'cards you closed today.',
  'help.parked': '💡 parked / +💡 Park',
  'help.parked.text': 'write down a new idea so it waits instead of starting work now.',
  'help.focus': '◎ focus',
  'help.focus.text': 'up to three projects for today; other cards wait unless a deadline is near.',
  'help.pages': '▦ pages',
  'help.pages.text': "the projects' own pages (a reply queue, a preview, a console), each with a dot: green answers, red does not. A red dot on the icon means one is down.",
  'help.sound': 'Sound',
  'help.sound.text': 'a short tone when you switch projects and a new card is first. Click once to enable.',
  'help.grey': 'Grey note',
  'help.grey.text': 'a known gap, not an error (e.g. a source that is not set up yet).',
  'help.yellow': 'Yellow note',
  'help.yellow.text': 'something could not be read — the card may be incomplete.',
  'help.tabs': 'Now | Goals | Calls',
  'help.tabs.text': 'the three tabs: the next card, the goals the work serves, and the calls to make. A number on Goals counts proposed goals awaiting your verdict, on Calls the calls to make (red when one is overdue); a triangle on a tab means that view could not be read.',
  'help.unconfirmed': 'Unconfirmed',
  'help.unconfirmed.text': 'a goal the publisher proposed. Keep it, say it is not a goal, or rename it; Suggestions below are its advice on what the goals should be.',
  'help.moon': 'Moon view',
  'help.moon.text': 'after the evening hour: write tomorrow\'s first card, hand things to night agents, park projects.',

  // ------------------------------------------------------------------ goals tab
  'goals.loadError': 'Goals could not load: {error}',
  'goals.readError': 'Goals could not be read',
  'goals.readErrorReason': 'Goals could not be read: {reason}',
  'goals.couldNotLoad': 'The goals could not be loaded',
  'goals.none': 'No goals are published',
  'goals.partialUnread': 'partial — the publisher could not read: {list}',
  'goals.partial': 'partial — the publisher says this list is incomplete',
  'goals.unread': 'the publisher could not read: {list}',
  'goals.stale': 'synthesised {age} ago',
  'goals.badGoals': { one: '{n} goal', other: '{n} goals' },
  'goals.badAdvice': { one: '{n} suggestion', other: '{n} suggestions' },
  'goals.and': ' and ',
  'goals.unreadable': '{what} unreadable, skipped',
  'goals.synthTitle': 'When the publisher last synthesised the goals',
  'goals.synth': 'synthesised {time} · ',
  'goals.count': { one: '{n} goal', other: '{n} goals' },
  'goals.toConfirm': ' · {n} to confirm',
  'goals.confirmed': ' · {n} confirmed',
  'goals.readOnly': 'Read-only — the publisher declares no owner-goals-act command, so it accepts no verdicts.',
  'goals.empty': 'The answer lists no goals.',
  'goals.serves': 'serves: {what}',
  'goals.unconfirmed': 'unconfirmed',
  'goals.unconfirmedTitle': 'Proposed by the publisher — not confirmed by you yet',
  'goals.deadline': 'Deadline',
  'goals.due': 'due {date}',
  'goals.openCards': { one: '{n} open card', other: '{n} open cards' },
  'goals.openCardsTitle': 'Open cards on the Now tab that serve this goal',
  'goals.renameLabel': 'New goal title',
  'goals.renameSave': 'Save',
  'goals.renameSaveTitle': 'Send the new title (Enter)',
  'goals.renameCancel': 'Cancel rename',
  'goals.keep': 'Keep',
  'goals.keepTitle': 'Yes, this is a goal — confirm it',
  'goals.rename': 'Rename',
  'goals.renameTitle': 'Keep it under a better title (Enter sends)',
  'goals.drop': 'Not a goal',
  'goals.dropTitle': 'This is not a goal — the publisher drops it',
  'goals.dropConfirmedTitle': 'This is no longer a goal — the publisher drops it',
  'goals.suggestions': 'Suggestions — what the goals should be',
  'goals.about': 'on "{title}" — ',
  'goals.accept': 'Accept',
  'goals.acceptTitle': 'Agree — the publisher applies this suggestion',
  'goals.decline': 'Decline',
  'goals.declineTitle': 'Disagree — the publisher keeps the goals as they are',
  'kind.add': 'add',
  'kind.drop': 'drop',
  'kind.merge': 'merge',
  'kind.reorder': 'reorder',
  'kind.neglected': 'neglected',
  'kind.other': 'other',
  'goalOutcome.keep': 'Goal kept',
  'goalOutcome.drop': 'Not a goal — sent',
  'goalOutcome.rename': 'Goal renamed',
  'goalOutcome.accept': 'Suggestion accepted',
  'goalOutcome.decline': 'Suggestion declined',
  'goalOutcome.notDelivered': 'Not delivered — nothing changed.',

  // ------------------------------------------------------------------ calls tab
  'tab.calls': 'Calls',
  'tab.callsTitle': 'Calls to make: promised callbacks, retries, missed calls',
  'tab.callsCountTitle': { one: '{n} call to make', other: '{n} calls to make' },
  'tab.callsOverdueTitle': { one: '{n} call to make — {overdue} overdue', other: '{n} calls to make — {overdue} overdue' },
  'tab.callsFail': 'The calls could not be read',
  'calls.loadError': 'Calls could not load: {error}',
  'calls.readError': 'Calls could not be read',
  'calls.readErrorReason': 'Calls could not be read: {reason}',
  'calls.couldNotLoad': 'The calls could not be loaded',
  'calls.none': 'No call list is published',
  'calls.empty': 'No calls to make.',
  'calls.partialUnread': 'partial — the publisher could not read: {list}',
  'calls.partial': 'partial — the publisher says this list is incomplete',
  'calls.unread': 'the publisher could not read: {list}',
  'calls.stale': 'listed {age} ago',
  'calls.bad': { one: '{n} call unreadable, skipped', other: '{n} calls unreadable, skipped' },
  'calls.listedTitle': 'When the publisher last listed the calls',
  'calls.listed': 'listed {time} · ',
  'calls.count': { one: '{n} call', other: '{n} calls' },
  'calls.overdueCount': ' · {n} overdue',
  'calls.readOnly': 'Read-only — the publisher declares no owner-calls-act command, so it accepts no answers.',
  'calls.kind.promised': 'promised',
  'calls.kind.retry': 'again',
  'calls.kind.missed': 'missed',
  'calls.kind.follow-up': 'follow-up',
  'calls.kindTitle.promised': 'You said you would call',
  'calls.kindTitle.retry': 'You called, nobody answered',
  'calls.kindTitle.missed': 'They called, you did not pick up',
  'calls.kindTitle.follow-up': 'A call is the next step of a matter',
  'calls.due': 'due {date}',
  'calls.overdue': 'overdue {date}',
  'calls.dueTitle': 'When the call was promised for',
  'calls.phoneTitle': 'Call this number',
  'calls.attempts': { one: '{n}× no answer', other: '{n}× no answer' },
  'calls.lastAttempt': ' · last {time}',
  'calls.called': 'Called',
  'calls.calledTitle': 'You called and talked — add a line on how it went (optional)',
  'calls.noteLabel': 'How did it go? (optional)',
  'calls.notePlaceholder': 'How did it go / next step… (Enter sends)',
  'calls.noteSend': 'Done',
  'calls.noteCancel': 'Cancel',
  'calls.noAnswer': 'No answer',
  'calls.noAnswerTitle': 'You called, nobody picked up — it comes back later',
  'calls.later': 'Later',
  'calls.laterTitle': 'Not now — hide it until…',
  'calls.notNeeded': 'Not needed',
  'calls.notNeededTitle': 'This call is not needed — it goes away for good',
  'callOutcome.called': 'Call recorded',
  'callOutcome.no-answer': 'No answer — it comes back later',
  'callOutcome.later': 'Snoozed',
  'callOutcome.not-needed': 'Removed — not needed',
  'callOutcome.notDelivered': 'Not delivered — nothing changed.',
} satisfies Record<string, Msg>

export type MsgKey = keyof typeof en

export const DICTIONARIES: Record<Locale, Record<MsgKey, Msg>> = { en, hu }

/** A value from the payload, narrowed: anything the card has no dictionary for reads as English. */
export function asLocale(value: unknown): Locale {
  return value === 'hu' ? 'hu' : 'en'
}

/** `{name}` → params.name. A placeholder with no value is left as written, so a gap is visible. */
function fill(text: string, params?: Params): string {
  if (!params) return text
  return text.replace(/\{(\w+)\}/g, (whole, name: string) => (name in params ? String(params[name]) : whole))
}

/**
 * One message. A `{ one, other }` message chooses by `params.n` (one only for exactly 1);
 * Hungarian entries are plain strings because the noun after a number stays singular.
 */
export function t(locale: Locale, key: MsgKey, params?: Params): string {
  const msg = (DICTIONARIES[locale] ?? DICTIONARIES.en)[key] ?? DICTIONARIES.en[key]
  const text = typeof msg === 'string' ? msg : (Number(params?.n) === 1 ? msg.one : msg.other)
  return fill(text, params)
}

export type T = (key: MsgKey, params?: Params) => string

/** `t` bound to one locale, for a component that renders many strings. */
export function makeT(locale: Locale): T {
  return (key, params) => t(locale, key, params)
}
