## Why

The Fleet screen's `+ start an agent` is dead on every Mac, and says so in a Linux
dialect: *"Start it with `systemctl --user start set-agent-owner.service`"*, naming a
socket at `/run/user/501/` on a machine that has neither. The agent owner was built
against systemd and never ported — `install.sh` places its unit in the Linux branch
only, the socket path falls back to `/run/user/<uid>`, and waiter measurement reads
`/proc`, so a Mac reports "the process table could not be read" forever.

The systemd branch of the installer already carries the argument for why this
matters, written for the case it did not cover: the installer must place the unit
"because the alternative is a screen whose start button is dead on every machine."
That is the state macOS has been in.

## What Changes

- **The owner runs as a launchd job on macOS**, installed and loaded by `install.sh`
  the way the systemd unit already is on Linux — a job of its own, never a child of
  the dashboard's.
- **The owner's socket path becomes platform-resolved** rather than
  `$XDG_RUNTIME_DIR`-or-`/run/user/<uid>`, and the resolved path is asserted to fit
  the platform's `sun_path` limit (104 bytes on macOS) instead of failing at bind
  time with a message about a missing directory.
- **`scopes.py` grows a platform backend boundary.** Its function API is kept; the
  systemd-transient-scope implementation becomes the Linux backend, and a macOS
  backend provides the same operations — start under a label, enumerate, stop by
  name, report liveness — over sessions and process groups, with its own on-disk
  record in place of systemd's unit registry.
- **The survival guarantee is restated as a platform-neutral requirement** with a
  platform-specific check. `assert_sibling()` asserts a cgroup relationship that has
  no macOS meaning; what it defends — an agent must not die when the dashboard is
  restarted — is the requirement, and each backend must verify it in terms its own
  kernel can answer.
- **Waiter measurement stops assuming `/proc`.** A macOS reader uses the process
  table the platform does expose (`ps`, and `lsof` for a working directory), and the
  three-way distinction the current code is careful about — measured-and-none,
  measured-and-some, could-not-measure — is preserved rather than widened.
- **Operator messages become platform-correct.** `START_COMMAND` is resolved per
  platform, so the screen never instructs a Mac user to run `systemctl`.
- Not in scope: changing what an agent is, how it is bound to a session, or anything
  the surface does once an agent exists. This change makes an existing capability
  reachable on a second platform; it adds no fleet behaviour.

## Capabilities

### New Capabilities

- `agent-owner-platform`: where the owner's socket lives, which service manager
  starts it on each platform, that the installer places that unit, and what an
  operator is told when it is not running.
- `agent-isolation-backend`: the survival guarantee an agent gets when started from
  the fleet, stated without reference to cgroups, plus the obligation on each
  platform backend to verify it at start rather than promise it.
- `waiter-measurement`: reading the waiter processes on a machine without `/proc`,
  keeping "could not measure" distinct from "there are none".

### Modified Capabilities

<!-- None. The owner's behaviour is unchanged where it already runs; no existing
     spec in openspec/specs/ states the owner's platform contract, so this change
     introduces it rather than amending one. -->

## Impact

- `lib/set_orch/fleet/scopes.py` — becomes a dispatching front for two backends.
- `lib/set_orch/fleet/ownerd.py` — `default_socket_path()`.
- `lib/set_orch/fleet/owner_client.py` — `START_COMMAND`.
- `lib/set_orch/fleet/owner.py` — reaches into `scopes` in ~15 places; the API it
  uses is preserved, so changes here should be confined to what the backend split
  forces.
- `lib/set_orch/fleet/instruct.py` — `live_waiters()` and its `/proc` helpers.
- `lib/set_orch/api/fleet.py` — the waiters endpoint's "could not measure" branch.
- `install.sh` — `install_launchd_service` gains the owner job; the systemd branch is
  left alone.
- `templates/launchd/` — a new plist, alongside the existing `com.set-core.web.plist`.
- No API shape changes on the wire, and no change to the web surface: the Fleet
  screen already renders every state this change makes reachable.
