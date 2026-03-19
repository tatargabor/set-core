# Proposal: Cumulative Review Feedback

## Problem

When the verify gate's LLM code review finds CRITICAL issues, the retry agent gets the review output and FILE:LINE:FIX instructions. But each retry only sees the **last** review — not what was tried before. After 3 retries the agent often cycles through the same approaches because it doesn't know what already failed.

CraftBrew Run #4 evidence: `auth-system` failed 3x on "middleware only checks cookie existence, not validity". The agent kept patching the same pattern instead of restructuring the approach.

## Solution

Add `review_history` to the change's state — an accumulating array of review attempts. Each entry captures: what the reviewer found, what fixes were extracted, and (after retry) what the agent changed. The retry prompt includes a squashed summary of ALL prior attempts, explicitly telling the agent what NOT to repeat.

## Scope

### In Scope
- `review_history` array field on change state (orchestration-state.json)
- Verifier appends review result after each CRITICAL finding
- Retry prompt builder reads full history and generates squashed summary
- "What NOT to repeat" section in retry prompt based on prior attempts
- Capture agent's diff between retry attempts as "what was tried"

### Out of Scope
- Cross-run persistence (future: extract to set-project-web rules at wrap-up)
- Memory system integration (future: auto-remember patterns)
- Changing review severity thresholds
- Increasing retry limits

## Expected Impact

- Retry agent sees full context: what was tried, what failed, why
- Fewer wasted retries on the same approach
- Higher fix rate for CRITICAL review issues (target: 50%+ on retry 2-3)
