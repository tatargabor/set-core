## IN SCOPE

- The optional `openTarget` card field: its shape (one project-root-relative path, file
  or directory), its absence behaviour, and the never-derived rule.
- The card click that follows a declared `openTarget` through the page's file view, and
  its reading-only guarantee.
- The page-level wiring: which element opens, and that full screen is left first.

## OUT OF SCOPE

- How a producer derives or names its canonical artefact field — the mapping is the
  producer's job; no producer field name enters framework code.
- Any write path from a card click — the board stays read-only.
- Opening anything not declared in the answer — no inference from `id`, `lane`, `path`
  or any other field.

## ADDED Requirements

### Requirement: The open target is declared by the producer, never derived
The card vocabulary SHALL carry an optional `openTarget`: a string holding the
project-root-relative path of the artefact the card IS — a file or a directory. set-core
MUST NOT derive an open target from any other card field, and MUST treat a value that is
not a non-empty string as absent. A card with no usable `openTarget` SHALL render as a
plain, non-clicking face.

#### Scenario: A card with no open target
- **WHEN** a card declares no `openTarget`, or declares one that is not a non-empty string
- **THEN** the card renders as a non-interactive face, and no control is offered for it

#### Scenario: The producer's other path-like fields are not opened
- **WHEN** a card carries producer-side fields that look like locations but no `openTarget`
- **THEN** the surface opens nothing for that card — the click would otherwise follow a
  source document rather than the artefact and look like it worked

### Requirement: Following a declared open target is a reading act
When the page provides an opener, a card that declares a usable `openTarget` SHALL render
as a control that opens that path through the page's file view. The click MUST NOT write
anything anywhere; the board's no-write-path guarantee is unchanged. When the page
provides no opener, even a card with a usable `openTarget` SHALL render as a plain face.

#### Scenario: A click on a declaring card
- **WHEN** the reader activates a card whose `openTarget` is `docs/bugs/ticket-42.md`
- **THEN** the page's file view opens that path, nothing is written anywhere, and no
  other field of the card is consulted to choose the target

#### Scenario: Full screen hands the reader back to the page
- **WHEN** the board is in full screen and the reader activates a declaring card
- **THEN** full screen is left and the file view opens in the page beneath — the artefact
  is never opened into a surface the reader cannot see

## MODIFIED Requirements

### Requirement: The board is read-only
The board view SHALL offer no write path. Every interaction it offers MUST be a reading
one (tooltips, scrolling, and opening a producer-declared `openTarget` through the page's
file view); planning changes to a card remain the project's own act, done in the
project's tools.

#### Scenario: A card click
- **WHEN** the reader clicks a card
- **THEN** nothing is written anywhere, and if the click has an effect it is a reading
  effect (showing more of the card's own text, or opening the artefact the producer
  declared as the card's `openTarget`), never a state change.
