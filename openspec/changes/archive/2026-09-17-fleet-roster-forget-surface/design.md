## Design

**The act already existed; only the surface is new.** `DELETE /api/fleet/roster/{project}/{key}`
→ `roster.forget` (drops one entry from the record document, atomic write) has
shipped since the roster. No framework change.

**Armed, like every act on this screen.** The restore control's own history
decides the shape: one mis-aimed click once started 21 agents. A destroy gets
no less. Both new controls are two-click: the first opens an amber question
carrying the blast radius (the entry's name; the ticked count), the second
acts. The armed question cannot outlive its selection — changing a tick or
closing the dialog disarms it.

**Copy states the true blast radius.** A forget removes the record entry only;
the transcript on disk stays. Every tooltip and confirm says so — a delete that
reads wider than it acts is a delete nobody dares press a second time.

**Sequential bulk deletes.** The record is one document rewritten per forget;
racing the writes would trade a slow delete for a lost one. Failures are
collected and shown together in the footer; successful keys are unticked and
the record is re-read once, after the loop — even a partial success changed the
record.

**A bug the tests caught, worth naming.** The first wiring passed the bare key
string where `forget(keys: string[])` expected a list; `for…of` iterated the
CHARACTERS, sending four DELETEs for `/O`, `/L`, `/D`, `/1`. The URL-asserting
test caught it before any live data was touched — the reason the tests assert
the exact request, not just that "a delete happened".

**Data markers** follow the screen's convention: `data-fleet-forget{,-confirm,-go}`,
`data-fleet-forget-all{,-confirm,-go}`, `data-fleet-forget-error`.
