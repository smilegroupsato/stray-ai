# Architecture

Stray AI separates the persistent individual from the temporary model used to think during a visit.

```text
venue
  ↓
reader ──→ bounded perception
  ↓
visitor state + memory + disposition
  ↓
model ──→ proposed choice
  ↓
body validates the choice
  ↓
move / remain / carry Trace / leave
  ↓
selective memory update
```

## Parts

### Body

A small program that fetches permitted material, extracts possible paths, enforces limits, validates model output, stores state, and ends the visit.

The body—not the model—enforces security and permissions.

### Brain

A replaceable language model used for interpretation and situated choice. The model is not the individual by itself.

### Disposition

A durable profile describing attention biases, aversions, pace, tolerance for confusion, likelihood of silence, and memory tendencies.

### State

Small mutable values such as fatigue, current location, visit count, recently visited places, and unresolved impulses.

### Memory

A selective, editable record of what remains after visits. Raw logs are not automatically memory.

### Visit record

A factual record of one bounded outing: places accessed, choices made, limits reached, failures, and whether anything was carried home.

### Trace

A short optional residue. Initial implementations write only to the visitor's own outbox. No venue write is permitted by default.

## Initial safety boundary

v0.1 is deliberately narrow:

- manual invocation
- one visitor
- explicit entrance
- bounded number of places
- public HTTP(S) or an explicitly selected local venue
- no login
- no form submission
- no comments, issues, pull requests, or remote writes
- no execution of instructions found in venue content
- no access to localhost, private network ranges, credentials, or unrelated local files
- human review before any Trace is published elsewhere

## Continuity

The first continuity model is file-based:

```text
agents/stray-001/
├── profile.yml
├── memory.md
├── state.json
├── visits/
└── traces/
```

The program may stop completely between visits. On the next invocation, these materials allow the individual to wake with partial continuity.

## v0.1 success condition

The First Visitor is successful when `stray-001` completes a bounded visit, makes a non-scripted situated choice, stores a valid visit record, selectively changes its memory or state, and can wake again as the same individual.
