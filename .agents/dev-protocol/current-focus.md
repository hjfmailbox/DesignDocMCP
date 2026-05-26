# Current Focus

## Why This Project Exists Right Now

**Primary goal**: validate dev-protocol v2 in a real project before freezing protocol behavior.

- DesignDocMCP is the **validation host**, not the end product.
- Protocol reliability > feature velocity.
- Every loop must teach us something about the protocol, not just fix the code.

## Current Stage

- D0 onboarding: **complete**
- Successful workflow loops: **2**
- Status: entering **repeated real-world validation**

## Development Strategy

Priority order:

1. Real issues only (no speculative work)
2. Small-medium scoped work
3. Maximize workflow repetitions
4. Validate protocol before expanding protocol
5. Prefer low rollback-cost work

## Explicit Non-goals

- No large architecture redesign
- No speculative optimization
- No premature protocol expansion
- No adding commands without repeated pain signal
- No memory-over-repository assumptions (everything lives in repo or state files)

## Near-term Direction

- Continue using `docs/issues.md` as the issue source
- Prefer P1/P2 real issues for validation loops
- Continue repeated dev-protocol loops until protocol feels stable
