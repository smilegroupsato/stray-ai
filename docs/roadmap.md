# Roadmap

## v0.1 — The First Visitor

- [x] Repository and package skeleton
- [x] First persistent individual
- [x] Bounded venue snapshot
- [x] First visit command
- [x] First local Trace through the deterministic observer
- [x] Visit Report v0 Phase 1
- [x] Bounded local LLM brain
- [x] First accepted local-LLM visit
- [x] Fail-closed visit observed on devbox
- [x] Coherent return migration validated on the persistent `stray-001`

## v0.1.1 — The First Persistent Visitor

- [x] Timeless memory bootstrap in repository template
- [x] `unborn`, `visiting`, and `resting` lifecycle semantics
- [x] Current presence separated from historical last location
- [x] Mock, LLM, accepted-brain, and safe-exit observation counters
- [x] Deterministic time-based fatigue recovery
- [x] Idempotent migration implementation
- [x] Devbox migration validation
- [x] Merge and close Issue #9

## v0.2 — The First Wake Judgment

- [x] Manual wake-check command
- [x] Conservative deterministic body gate
- [x] Opaque snapshot-change detection without venue-content reading
- [x] Persistent wake-check JSON
- [x] Bounded command-brain protocol
- [x] Fail-closed sleep on invalid or unavailable brain
- [x] At-most-one deduplicated unresolved impulse
- [x] Offline tests
- [x] CI validation
- [x] Devbox check against the current local snapshot
- [x] Merge and close Issue #11

## Visit Report v0

- [x] Phase 1 — one visit as one HTML page
- [x] Phase 2 — static chronological visit index
- [x] Relative-link and HTTP-independent generation
- [x] Empty and malformed archive handling
- [x] Phase 2 CI validation
- [x] Phase 2 devbox validation against four preserved visits
- [x] Merge and close Issue #13
- [x] Phase 2.1 implementation — trusted source coordinates
- [x] Commit-fixed page permalinks without Visit JSON mutation
- [x] Relative return navigation from every Visit Report to `index.html`
- [x] Graceful fallback for old or untrusted records
- [x] Phase 2.1 CI validation
- [x] Phase 2.1 devbox and browser validation
- [x] Merge and close Issue #15
- [x] Phase 3 implementation — observed venue map
- [x] Static SVG plus accessible route and page tables
- [x] Group trusted venues by repository and observed commit
- [x] Preserve local-only venues without fabricated coordinates
- [x] Phase 3 CI validation
- [x] Phase 3 devbox and browser validation
- [x] Phase 3 merge and close Issue #17
- [x] Phase 4 implementation — multiple-individual report collection
- [x] Isolated report namespaces per individual
- [x] Primary root compatibility for `latest.html`, `map.html`, and named Reports
- [x] Read-only collection entrance without memory or local-path exposure
- [x] Phase 4 CI validation
- [x] Phase 4 devbox and browser validation
- [x] Phase 4 merge and close Issue #19
- [x] Phase 5 design — observed world map boundary
- [x] Phase 5 implementation — `world.html`
- [x] Aggregate individual-to-observed-place relationships without inferred travel
- [x] Preserve exact commit separation and local-only isolation
- [x] Add accessible evidence and place tables
- [x] Link collection entrance and world map with relative URLs
- [x] Phase 5 CI validation
- [x] Phase 5 devbox, source-preservation, and Gateway validation
- [x] Phase 5 browser inspection
- [x] Phase 5 merge and close Issue #21

## Venue Operations v0

- [x] Define GENAI-RON Repository Context as the second bounded venue
- [x] Fix the approved manifest to `README.md`, `CHAT_HISTORY.md`, and `AFTERHOURS.md`
- [x] Add commit-addressed snapshot creation with fail-closed validation
- [x] Separate snapshot preparation from manual mock and LLM Visit launchers
- [x] Preserve a bounded trusted venue display label in Visit Reports
- [x] Offline tests and CI validation
- [x] Devbox snapshot-only validation and manifest inspection
- [x] Merge and close Issue #23
- [x] First separately approved GENAI-RON Visit

## Memory provenance v0

- [x] Keep `memory.md` as the human-readable continuity layer
- [x] Add append-only `memory_records.jsonl`
- [x] Separate `recorded_at`, source Visit, and source step from memory text
- [x] Preserve embedded model-authored timestamps as untrusted text
- [x] Add idempotent historical backfill without Visit mutation
- [x] Add offline regression tests
- [x] CI validation
- [x] Devbox backfill validation against preserved `stray-001`
- [x] Merge and close Issue #25

## Wake-to-Visit Handoff v0

- [x] Define an approval-only handoff boundary
- [x] Validate accepted local `request_visit` wake records
- [x] Require a human-supplied existing snapshot and bounded route
- [x] Add idempotent `pending_human_approval` envelopes
- [x] Keep state, Visit, wake, memory, Trace, and reports unchanged
- [x] Exclude `run_visit`, schedulers, auto-approval, fetch, and venue-content reads
- [x] Add offline fail-closed regression tests
- [x] CI validation
- [x] Synthetic devbox validation without running wake or Visit
- [x] Merge and close Issue #29

## Human-approved Visit Execution v0

- [x] Separate explicit approval from explicit execution
- [x] Require exact request-id confirmation and a named approver
- [x] Bind snapshot, route, outbox, backend, and brain plan at approval
- [x] Protect the approval with a canonical SHA-256 digest
- [x] Revalidate source wake, request core, route, and resting state before execution
- [x] Add a durable exclusive execution claim
- [x] Prevent automatic retry after failure or interruption
- [x] Record the resulting Visit file after success
- [x] Add offline mock and command-brain regression tests
- [ ] CI validation
- [ ] Synthetic devbox approval and one-shot Visit validation
- [ ] Merge and close Issue #31

## After one-shot execution

A later review may define human-facing approval presentation, fail-stop recovery, or request cancellation. No scheduler, automatic approval, automatic retry, automatic snapshot fetch, or automatic Visit is part of the current milestone.
